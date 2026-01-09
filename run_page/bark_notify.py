#!/usr/bin/env python3
"""
Simple script to send weekly/monthly/yearly running stats to Bark.
Reads data directly from src/static/activities.json (exported from data.db).

local test:
python run_page/bark_notify.py \
  --bark-url "https://api.day.app/YOUR_BARK_KEY"
"""

import json
import sys
import argparse
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


def get_date_ranges() -> Tuple[str, str, str, str]:
    """Get start dates for week, month, year and today."""
    today = datetime.now()

    # This week (Monday of current week)
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

    # This month (1st day of current month)
    month_start = today.strftime("%Y-%m-01")

    # This year (Jan 1st)
    year_start = today.strftime("%Y-01-01")

    today_str = today.strftime("%Y-%m-%d")

    return week_start, month_start, year_start, today_str


def load_activities(json_file: str) -> List[Dict]:
    """Load activities from JSON file."""
    try:
        with open(json_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {json_file} not found")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_file}")
        return []


def filter_by_date(
    activities: List[Dict], start_date: str, end_date: str
) -> List[Dict]:
    """Filter activities by date range."""
    result = []
    for activity in activities:
        activity_date = activity.get("start_date_local", "")[:10]
        if start_date <= activity_date <= end_date:
            result.append(activity)
    return result


def calculate_stats(activities: List[Dict]) -> Dict:
    """Calculate statistics from activities."""
    if not activities:
        return {"distance_km": 0.0, "count": 0, "moving_time": 0, "pace": "N/A"}

    total_distance = sum(a.get("distance", 0) for a in activities) / 1000  # to km
    count = len(activities)

    # Calculate moving time (in seconds)
    total_time = 0
    for activity in activities:
        moving_time = activity.get("moving_time")
        if moving_time:
            if isinstance(moving_time, str):
                # Parse "H:MM:SS.ffffff" or "0:MM.ffffff" format
                parts = moving_time.split(":")
                if len(parts) == 2:
                    # Format: "M:SS.ffffff"
                    hours = int(parts[0])
                    minutes_seconds = float(parts[1])
                    total_time += hours * 3600 + int(minutes_seconds * 60)
                elif len(parts) == 3:
                    # Format: "H:MM:SS.ffffff"
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = float(parts[2])
                    total_time += hours * 3600 + minutes * 60 + int(seconds)
            elif isinstance(moving_time, (int, float)):
                total_time += int(moving_time)

    # Calculate pace
    if total_distance > 0 and total_time > 0:
        seconds_per_km = total_time / total_distance
        minutes = int(seconds_per_km // 60)
        seconds = int(seconds_per_km % 60)
        pace = f"{minutes}:{seconds:02d}/km"
    else:
        pace = "N/A"

    return {
        "distance_km": total_distance,
        "count": count,
        "moving_time": total_time,
        "pace": pace,
    }


def format_time(seconds: int) -> str:
    """Format seconds to HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def generate_message(week_stats: Dict, month_stats: Dict, year_stats: Dict) -> str:
    """Generate notification message for running statistics."""
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    month_str = today.strftime("%Y-%m")
    year_str = today.strftime("%Y")

    lines = [
        f"📅 This Week ({week_start} ~ {today_str}):",
        f"   Distance: {week_stats['distance_km']:.2f} km",
        f"   Runs: {week_stats['count']}",
    ]

    if week_stats["count"] > 0:
        lines.append(f"   Time: {format_time(week_stats['moving_time'])}")
        lines.append(f"   Pace: {week_stats['pace']}")

    lines.extend(
        [
            "",
            f"📊 This Month ({month_str}):",
            f"   Distance: {month_stats['distance_km']:.2f} km",
            f"   Runs: {month_stats['count']}",
        ]
    )

    if month_stats["count"] > 0:
        lines.append(f"   Time: {format_time(month_stats['moving_time'])}")
        lines.append(f"   Pace: {month_stats['pace']}")

    lines.extend(
        [
            "",
            f"🎯 This Year ({year_str}):",
            f"   Distance: {year_stats['distance_km']:.2f} km",
            f"   Runs: {year_stats['count']}",
        ]
    )

    if year_stats["count"] > 0:
        lines.append(f"   Time: {format_time(year_stats['moving_time'])}")
        lines.append(f"   Pace: {year_stats['pace']}")

    return "\n".join(lines)


def send_to_bark(bark_url: str, title: str, body: str) -> bool:
    """Send notification to Bark with group and URL parameters."""
    try:
        # Bark API: GET https://api.day.app/{KEY}/TITLE/BODY?group=GROUP&icon=ICON
        # Hardcoded group and icon for running stats
        group = "Running Page"
        icon = "https://raw.githubusercontent.com/yihong0618/running_page/refs/heads/master/public/images/favicon.png"

        # Simple encoding - avoid double encoding
        encoded_title = urllib.parse.quote(title, safe="")
        encoded_body = urllib.parse.quote(body, safe="")

        # Ensure URL ends with /
        if bark_url.endswith("/"):
            url_base = f"{bark_url}{encoded_title}/{encoded_body}"
        else:
            url_base = f"{bark_url}/{encoded_title}/{encoded_body}"

        # Build query string with group and icon
        params = {"group": group, "icon": icon}
        query_string = urllib.parse.urlencode(params)
        final_url = f"{url_base}?{query_string}"

        # Create request
        req = urllib.request.Request(final_url)
        req.add_header("User-Agent", "Mozilla/5.0")

        # Send request
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("✓ Bark notification sent successfully")
                return True
            else:
                print(f"✗ HTTP {response.status}: {response.reason}")
                return False

    except urllib.error.HTTPError as e:
        # 404 usually means bad key
        if e.code == 404:
            print("✗ Bark API Key invalid (404 Not Found)", file=sys.stderr)
        else:
            print(f"✗ HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Send running stats to Bark")
    parser.add_argument("--bark-url", required=True, help="Bark service URL")
    parser.add_argument(
        "--json-file",
        default="src/static/activities.json",
        help="Path to activities JSON file",
    )
    args = parser.parse_args()

    # Load activities
    activities = load_activities(args.json_file)
    if not activities:
        print("No activities found in JSON file")
        return 1

    # Get date ranges
    week_start, month_start, year_start, today_str = get_date_ranges()

    # Calculate stats
    week_activities = filter_by_date(activities, week_start, today_str)
    month_activities = filter_by_date(activities, month_start, today_str)
    year_activities = filter_by_date(activities, year_start, today_str)

    week_stats = calculate_stats(week_activities)
    month_stats = calculate_stats(month_activities)
    year_stats = calculate_stats(year_activities)

    # Generate and print message
    message = generate_message(week_stats, month_stats, year_stats)
    print(message)

    # Send to Bark
    print("\nSending to Bark...")
    if send_to_bark(args.bark_url, "Running Summary", message):
        print("✓ Sent successfully")
        return 0
    else:
        print("✗ Failed to send")
        return 1


if __name__ == "__main__":
    sys.exit(main())
