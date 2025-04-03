#!/usr/bin/env python3
"""
Cargo Stowage Management System – Backend Application

This Flask application exposes the following API endpoints on port 8000:

1. /api/placement (POST): Suggests placement recommendations for new items
   based on containers and item preferred zones.
2. /api/search (GET): Searches for an item by itemId or itemName; returns
   retrieval instructions.
3. /api/retrieve (POST): Logs retrieval of an item (increments item usage).
4. /api/place (POST): Updates an item's location (container and position).
5. /api/waste/identify (GET): Identifies items that have expired (or are out of uses)
   – these are categorized as waste.
6. /api/waste/return-plan (POST): Generates a dummy return plan for waste items,
   moving them to the undocking container.
7. /api/waste/complete-undocking (POST): Completes the undocking process and removes waste items.
8. /api/simulate/day (POST): Simulates the passing of one or more days by advancing
   the simulation date and updating use counts.
9. /api/import/items (POST): Imports items from an uploaded CSV file.
10. /api/import/containers (POST): Imports container definitions from an uploaded CSV.
11. /api/export/arrangement (GET): Exports the current arrangement as a CSV file.
12. /api/logs (GET): Returns logs for a given date range and optional filters.

For Docker-based deployment the application listens on 0.0.0.0:8000.
"""

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from datetime import datetime, timedelta
import csv
import io

app = Flask(__name__)
CORS(app)

# Global in-memory data structures
items_db = {}         # key: itemId, value: item details dictionary
containers_db = {}    # key: containerId, value: container details dictionary
logs_list = []        # list of log entries

# Simulation current date (for time simulation purposes)
current_simulation_date = datetime.utcnow()

# ---------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------
def log_action(action, details):
    """Record an action along with details into the global logs list."""
    entry = {"timestamp": datetime.utcnow().isoformat(), "action": action}
    entry.update(details)
    logs_list.append(entry)

# ---------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------

# 1. Placement Recommendations API
@app.route("/api/placement", methods=["POST"])
def placement():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
    
    items = data.get("items", [])
    containers = data.get("containers", [])
    placements = []
    rearrangements = []  # This demo does not compute rearrangements

    # Populate containers global dictionary
    for container in containers:
        containers_db[container["containerId"]] = container

    # For each item assign a container and dummy placement
    for item in items:
        # Try to match container by preferredZone; otherwise take the first container available.
        chosen_container = None
        for container in containers:
            if container.get("zone") == item.get("preferredZone"):
                chosen_container = container
                break
        if not chosen_container and containers:
            chosen_container = containers[0]

        container_id = chosen_container.get("containerId") if chosen_container else "N/A"
        # Dummy placement: origin (0,0,0), endCoordinates based on item dimensions.
        position = {
            "startCoordinates": {"width": 0, "depth": 0, "height": 0},
            "endCoordinates": {
                "width": item.get("width", 0),
                "depth": item.get("depth", 0),
                "height": item.get("height", 0)
            }
        }
        placements.append({
            "itemId": item.get("itemId"),
            "containerId": container_id,
            "position": position
        })
        # Store the item in the global database, including a usage counter.
        items_db[item.get("itemId")] = {
            "itemId": item.get("itemId"),
            "name": item.get("name"),
            "width": item.get("width"),
            "depth": item.get("depth"),
            "height": item.get("height"),
            "mass": item.get("mass", 0),
            "priority": item.get("priority"),
            "expiryDate": item.get("expiryDate"),  # assumed ISO format or "N/A"
            "usageLimit": item.get("usageLimit"),
            "preferredZone": item.get("preferredZone"),
            "containerId": container_id,
            "position": position,
            "uses": 0
        }
        log_action("placement", {"itemId": item.get("itemId"), "containerId": container_id})
    
    return jsonify({"success": True, "placements": placements, "rearrangements": rearrangements})


# 2. Item Search API
@app.route("/api/search", methods=["GET"])
def search():
    item_id = request.args.get("itemId")
    item_name = request.args.get("itemName")
    user_id = request.args.get("userId", "")
    found_item = None

    if item_id and item_id in items_db:
        found_item = items_db[item_id]
    elif item_name:
        for itm in items_db.values():
            if itm.get("name", "").lower() == item_name.lower():
                found_item = itm
                break
    
    if found_item:
        # For demo, assume retrieval steps are empty if the item is at the container's open-face.
        retrievalSteps = []
        log_action("search", {"userId": user_id, "itemId": found_item.get("itemId")})
        return jsonify({"success": True, "found": True, "item": found_item, "retrievalSteps": retrievalSteps})
    else:
        return jsonify({"success": True, "found": False, "message": "Item not found", "retrievalSteps": []})


# 3. Item Retrieval API – logs a retrieval action and increments item usage count.
@app.route("/api/retrieve", methods=["POST"])
def retrieve():
    data = request.get_json()
    itemId = data.get("itemId")
    userId = data.get("userId")
    timestamp = data.get("timestamp")
    
    if not itemId or itemId not in items_db:
        return jsonify({"success": False, "message": "Invalid itemId"})
    
    item = items_db.get(itemId)
    item["uses"] = item.get("uses", 0) + 1
    log_action("retrieve", {"userId": userId, "itemId": itemId, "timestamp": timestamp})
    return jsonify({"success": True})


# 4. Placement Update API - update an item's container and position.
@app.route("/api/place", methods=["POST"])
def place():
    data = request.get_json()
    itemId = data.get("itemId")
    userId = data.get("userId")
    timestamp = data.get("timestamp")
    containerId = data.get("containerId")
    position = data.get("position")
    
    if not itemId or itemId not in items_db:
        return jsonify({"success": False, "message": "Invalid itemId"})
    
    item = items_db.get(itemId)
    item["containerId"] = containerId
    item["position"] = position
    log_action("place", {"userId": userId, "itemId": itemId, "containerId": containerId, "timestamp": timestamp})
    return jsonify({"success": True})


# 5. Waste Management API – Identify waste items.
@app.route("/api/waste/identify", methods=["GET"])
def waste_identify():
    wasteItems = []
    current_time = datetime.utcnow()
    for item in items_db.values():
        is_waste = False
        reason = ""
        expiry_str = item.get("expiryDate")
        if expiry_str and expiry_str != "N/A":
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                if current_time > expiry_dt:
                    is_waste = True
                    reason = "Expired"
            except Exception:
                pass
        # Check if the item uses have reached its usageLimit.
        usageLimit = item.get("usageLimit")
        if usageLimit is not None and item.get("uses", 0) >= usageLimit:
            is_waste = True
            reason = "Out of Uses"
        if is_waste:
            wasteItems.append({
                "itemId": item.get("itemId"),
                "name": item.get("name"),
                "reason": reason,
                "containerId": item.get("containerId"),
                "position": item.get("position")
            })
    return jsonify({"success": True, "wasteItems": wasteItems})


# 6. Waste Return Plan API – Generate a plan to move waste into the undocking module.
@app.route("/api/waste/return-plan", methods=["POST"])
def waste_return_plan():
    data = request.get_json()
    undockingContainerId = data.get("undockingContainerId")
    undockingDate = data.get("undockingDate")
    maxWeight = data.get("maxWeight")
    
    waste_items = []
    for item in items_db.values():
        is_waste = False
        expiry_str = item.get("expiryDate")
        if expiry_str and expiry_str != "N/A":
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                if datetime.utcnow() > expiry_dt:
                    is_waste = True
            except:
                pass
        if item.get("usageLimit") is not None and item.get("uses", 0) >= item.get("usageLimit"):
            is_waste = True
        if is_waste:
            waste_items.append(item)
    
    returnPlan = []
    retrievalSteps = []
    step = 1
    totalVolume = 0
    totalWeight = 0
    for waste in waste_items:
        returnPlan.append({
            "step": step,
            "itemId": waste.get("itemId"),
            "itemName": waste.get("name"),
            "fromContainer": waste.get("containerId"),
            "toContainer": undockingContainerId
        })
        step += 1
        volume = waste.get("width", 0) * waste.get("depth", 0) * waste.get("height", 0)
        totalVolume += volume
        totalWeight += waste.get("mass", 0)
    
    returnManifest = {
        "undockingContainerId": undockingContainerId,
        "undockingDate": undockingDate,
        "returnItems": [{"itemId": waste.get("itemId"), "name": waste.get("name"), "reason": "Waste"} for waste in waste_items],
        "totalVolume": totalVolume,
        "totalWeight": totalWeight
    }
    log_action("waste_return_plan", {"undockingContainerId": undockingContainerId})
    return jsonify({
        "success": True,
        "returnPlan": returnPlan,
        "retrievalSteps": retrievalSteps,
        "returnManifest": returnManifest
    })


# 7. Waste Management – Complete Undocking API.
@app.route("/api/waste/complete-undocking", methods=["POST"])
def complete_undocking():
    data = request.get_json()
    undockingContainerId = data.get("undockingContainerId")
    timestamp = data.get("timestamp")
    
    items_to_remove = []
    for item_id, item in list(items_db.items()):
        is_waste = False
        expiry_str = item.get("expiryDate")
        if expiry_str and expiry_str != "N/A":
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                if datetime.utcnow() > expiry_dt:
                    is_waste = True
            except:
                pass
        if item.get("usageLimit") is not None and item.get("uses", 0) >= item.get("usageLimit"):
            is_waste = True
        if is_waste and item.get("containerId") == undockingContainerId:
            items_to_remove.append(item_id)
    for item_id in items_to_remove:
        del items_db[item_id]
    
    log_action("complete_undocking", {"undockingContainerId": undockingContainerId, "timestamp": timestamp})
    return jsonify({"success": True, "itemsRemoved": len(items_to_remove)})


# 8. Time Simulation API – Simulate the passing of days.
@app.route("/api/simulate/day", methods=["POST"])
def simulate_day():
    global current_simulation_date
    data = request.get_json()
    # "days": number of days to advance; "itemsUsed": list of itemIds used during this period.
    days = data.get("days", 1)
    itemsUsed = data.get("itemsUsed", [])
    
    current_simulation_date += timedelta(days=days)
    for itemId in itemsUsed:
        if itemId in items_db:
            items_db[itemId]["uses"] = items_db[itemId].get("uses", 0) + 1
    log_action("simulate_day", {"days": days, "itemsUsed": itemsUsed, "newDate": current_simulation_date.isoformat()})
    changes = {"itemsUsed": itemsUsed}
    return jsonify({"success": True, "newDate": current_simulation_date.isoformat(), "changes": changes})


# 9. Import Items API – Import items via CSV file upload.
@app.route("/api/import/items", methods=["POST"])
def import_items():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Empty filename"}), 400
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        count = 0
        errors = []
        for row in csv_input:
            try:
                item_id = row["Item ID"]
                items_db[item_id] = {
                    "itemId": item_id,
                    "name": row["Name"],
                    "width": float(row["Width (cm)"]),
                    "depth": float(row["Depth (cm)"]),
                    "height": float(row["Height (cm)"]),
                    "mass": float(row["Mass (kg)"]),
                    "priority": int(row["Priority"]),
                    "expiryDate": row["Expiry Date (ISO Format)"],
                    "usageLimit": int(row["Usage Limit"].split()[0]) if "uses" in row["Usage Limit"].lower() else int(row["Usage Limit"]),
                    "preferredZone": row["Preferred Zone"],
                    "containerId": None,
                    "position": {
                        "startCoordinates": {"width": 0, "depth": 0, "height": 0},
                        "endCoordinates": {"width": 0, "depth": 0, "height": 0}
                    },
                    "uses": 0
                }
                count += 1
            except Exception as e:
                errors.append({"row": count + 1, "message": str(e)})
        log_action("import_items", {"itemsImported": count})
        return jsonify({"success": True, "itemsImported": count, "errors": errors})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# 10. Import Containers API – Import container definitions via CSV file upload.
@app.route("/api/import/containers", methods=["POST"])
def import_containers():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "Empty filename"}), 400
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        count = 0
        errors = []
        for row in csv_input:
            try:
                container_id = row["Container ID"]
                containers_db[container_id] = {
                    "containerId": container_id,
                    "zone": row["Zone"],
                    "width": float(row["Width(cm)"]),
                    "depth": float(row["Depth(cm)"]),
                    "height": float(row["Height(height)"])
                }
                count += 1
            except Exception as e:
                errors.append({"row": count + 1, "message": str(e)})
        log_action("import_containers", {"containersImported": count})
        return jsonify({"success": True, "containersImported": count, "errors": errors})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# 11. Export Arrangement API – Download the current arrangement as a CSV file.
@app.route("/api/export/arrangement", methods=["GET"])
def export_arrangement():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Item ID", "Container ID", "Coordinates (W,D,H)", "Coordinates (W2,D2,H2)"])
    for item in items_db.values():
        pos = item.get("position", {})
        start = pos.get("startCoordinates", {})
        end = pos.get("endCoordinates", {})
        writer.writerow([
            item.get("itemId"),
            item.get("containerId"),
            f"({start.get('width')},{start.get('depth')},{start.get('height')})",
            f"({end.get('width')},{end.get('depth')},{end.get('height')})"
        ])
    output.seek(0)
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=arrangement.csv"})


# 12. Logging API – Retrieve logs with optional filtering.
@app.route("/api/logs", methods=["GET"])
def get_logs():
    startDate = request.args.get("startDate")
    endDate = request.args.get("endDate")
    itemId = request.args.get("itemId", None)
    userId = request.args.get("userId", None)
    actionType = request.args.get("actionType", None)
    
    filtered_logs = logs_list.copy()
    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate)
            filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log["timestamp"]) >= start_dt]
        except Exception:
            pass
    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate)
            filtered_logs = [log for log in filtered_logs if datetime.fromisoformat(log["timestamp"]) <= end_dt]
        except Exception:
            pass
    if itemId:
        filtered_logs = [log for log in filtered_logs if log.get("itemId") == itemId]
    if userId:
        filtered_logs = [log for log in filtered_logs if log.get("userId") == userId]
    if actionType:
        filtered_logs = [log for log in filtered_logs if log.get("action") == actionType]
    
    return jsonify({"success": True, "logs": filtered_logs})


# ---------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------
if __name__ == '__main__':
    # Ensure the app listens on 0.0.0.0 and port 8000 to meet Docker requirements.
    app.run(host="0.0.0.0", port=8000, debug=True)
