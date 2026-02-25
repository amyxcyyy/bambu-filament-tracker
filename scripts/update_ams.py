#!/usr/bin/env python3
"""Fetch AMS filament status from Bambu Lab Cloud MQTT and update data files."""

import json
import os
import sys
import time
from datetime import datetime, timezone

def main():
    from bambulab import MQTTClient

    token = os.environ.get("BAMBU_TOKEN")
    uid = os.environ.get("BAMBU_UID")
    serial = os.environ.get("BAMBU_SERIAL")

    if not all([token, uid, serial]):
        print("Error: BAMBU_TOKEN, BAMBU_UID, and BAMBU_SERIAL must be set")
        sys.exit(1)

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    ams_file = os.path.join(data_dir, "ams_status.json")

    # Load existing data for history tracking
    history_file = os.path.join(data_dir, "usage_history.json")
    if os.path.exists(history_file):
        with open(history_file) as f:
            history = json.load(f)
    else:
        history = {"updates": []}

    ams_data = None

    def on_message(device_id, data):
        nonlocal ams_data
        if "print" in data and "ams" in data["print"]:
            ams_data = data["print"]["ams"]

    print(f"Connecting to printer {serial} via cloud MQTT...")
    mqtt = MQTTClient(uid, token, serial, on_message=on_message)
    mqtt.connect(blocking=False)

    # Wait up to 20 seconds for AMS data
    for i in range(40):
        time.sleep(0.5)
        if ams_data:
            break

    try:
        mqtt.disconnect()
    except:
        pass

    if not ams_data:
        print("No AMS data received. Printer may be offline.")
        sys.exit(1)

    # Process AMS data
    now = datetime.now(timezone.utc).isoformat()
    trays = []
    for unit in ams_data.get("ams", []):
        ams_id = unit.get("ams_id", "")
        humidity = unit.get("humidity", "")
        temp = unit.get("temp", "")
        for tray in unit.get("tray", []):
            trays.append({
                "tray_id": tray.get("id"),
                "tray_id_name": tray.get("tray_id_name", ""),
                "tray_type": tray.get("tray_type", ""),
                "tray_sub_brands": tray.get("tray_sub_brands", ""),
                "tray_color": tray.get("tray_color", ""),
                "remain": tray.get("remain", 0),
                "tray_weight": tray.get("tray_weight", ""),
                "tag_uid": tray.get("tag_uid", ""),
                "tray_uuid": tray.get("tray_uuid", ""),
            })

    status = {
        "last_updated": now,
        "printer_serial": serial,
        "trays": trays,
    }

    # Save current status
    with open(ams_file, "w") as f:
        json.dump(status, f, indent=2)
    print(f"AMS status saved: {len(trays)} trays found")

    # Append to history (keep last 500 entries to avoid bloat)
    history_entry = {"timestamp": now, "trays": trays}
    history["updates"].append(history_entry)
    history["updates"] = history["updates"][-500:]
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)
    print(f"History updated: {len(history['updates'])} entries")

    # Print summary
    for t in trays:
        color = t["tray_color"][:6] if t["tray_color"] else "------"
        print(f"  Tray {t['tray_id']}: {t['tray_sub_brands']} ({t['tray_id_name']}) #{color} - {t['remain']}% remaining")

if __name__ == "__main__":
    main()
