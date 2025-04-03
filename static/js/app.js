document.addEventListener('DOMContentLoaded', function () {
  init();
});

function init() {
  bindUIEvents();
  // Load initial map from the selector value
  const mapSelector = document.getElementById('map-selector');
  loadMap(mapSelector.value);
  loadCSVDataFromMap(mapSelector.value);
  // Fetch logs immediately and then every 30 seconds
  fetchLogs();
  setInterval(fetchLogs, 30000);
}

function bindUIEvents() {
  document.getElementById('open-sidebar').addEventListener('click', openSidebar);
  document.getElementById('close-sidebar').addEventListener('click', closeSidebar);
  document.getElementById('map-selector').addEventListener('change', function (e) {
    const selectedMap = e.target.value;
    loadMap(selectedMap);
    loadCSVDataFromMap(selectedMap);
  });
  document.getElementById('supply-request-form').addEventListener('submit', handleSupplyRequest);
}

function openSidebar() {
  document.getElementById('sidebar').classList.add('active');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('active');
}

function loadMap(mapImgName) {
  // Update the map container background image (from the maps folder)
  const mapContainer = document.getElementById('main-map');
  mapContainer.style.backgroundImage = `url('/maps/${mapImgName}')`;
}

function loadCSVDataFromMap(mapImgName) {
  // Derive CSV file name from map name (e.g., map1.png -> map1.csv)
  const baseName = mapImgName.split('.')[0];
  const csvUrl = `/data/${baseName}.csv`;

  fetch(csvUrl)
    .then(response => {
      if (!response.ok) {
        throw new Error(`CSV file not found: ${csvUrl}`);
      }
      return response.text();
    })
    .then(text => {
      const data = parseCSV(text);
      renderItems(data);
    })
    .catch(error => console.error("Error loading CSV: ", error));
}

// Simple CSV parser assuming no commas within field values.
function parseCSV(text) {
  const lines = text.trim().split("\n");
  const headers = lines[0].split(',').map(h => h.trim());
  const result = [];
  for (let i = 1; i < lines.length; i++) {
    const row = lines[i].split(',').map(c => c.trim());
    const obj = {};
    headers.forEach((header, index) => {
      obj[header] = row[index];
    });
    result.push(obj);
  }
  return result;
}

function renderItems(items) {
  const container = document.getElementById('item-container');
  container.innerHTML = ''; // Clear any previous items

  items.forEach(item => {
    // Expect centre_coordinates in the format "x,y" (percentage values)
    const coordinates = item.centre_coordinates.split(',');
    const leftPercent = parseFloat(coordinates[0]);
    const topPercent = parseFloat(coordinates[1]);

    // Create a div to represent the item on the map
    const div = document.createElement('div');
    div.classList.add('map-item');

    // Dimensions (assume length and breadth are in pixels)
    const width = parseFloat(item.length);
    const height = parseFloat(item.breadth);
    div.style.width = `${width}px`;
    div.style.height = `${height}px`;

    // Position the element so that its center aligns with given coordinates.
    // Calculate the pixel position based on the container's dimensions.
    const containerWidth = container.offsetWidth;
    const containerHeight = container.offsetHeight;
    const leftPos = (leftPercent / 100 * containerWidth) - (width / 2);
    const topPos = (topPercent / 100 * containerHeight) - (height / 2);
    div.style.left = `${leftPos}px`;
    div.style.top = `${topPos}px`;

    // Calculate expiry information
    const timeInfo = getTimeLeft(item.Expiry_Date);
    // Set background color based on time left (for visual urgency)
    div.style.backgroundColor = getColorFromTime(timeInfo.hoursLeft);

    // Event listeners for tooltip display
    div.addEventListener('mouseenter', function (e) {
      showTooltip(item, timeInfo, e);
    });
    div.addEventListener('mouseleave', hideTooltip);

    container.appendChild(div);
  });
}

// Computes the time left for expiry using the ISO expiry date.
// Returns an object with text for display and hoursLeft (a number).
function getTimeLeft(expiry) {
  if (expiry === "N/A" || !expiry) {
    return { text: "No Expiry", hoursLeft: Infinity };
  }
  const expiryDate = new Date(expiry);
  const now = new Date();
  const diffMs = expiryDate - now;
  const diffHours = diffMs / (1000 * 60 * 60);
  if (diffHours < 0) {
    return { text: "Expired", hoursLeft: 0 };
  }
  return { text: `Expires in ${Math.floor(diffHours)} hours`, hoursLeft: diffHours };
}

// Returns a color code based on the hours left until expiry.
function getColorFromTime(hoursLeft) {
  if (hoursLeft === Infinity) return "#3498db"; // Blue when no expiry
  if (hoursLeft <= 0) return "#7f8c8d"; // Grey if already expired
  if (hoursLeft < 24) return "#e74c3c"; // Red for urgent/soon expiry
  if (hoursLeft < 72) return "#f1c40f"; // Yellow for moderate time left
  return "#2ecc71"; // Green for plenty of time left
}

// Displays a tooltip near the mouse pointer with item details.
function showTooltip(item, timeInfo, event) {
  const tooltip = document.getElementById('tooltip');
  tooltip.innerHTML = `<strong>${item.item_type} - ${item.item_name}</strong><br>${timeInfo.text}`;
  tooltip.style.left = (event.pageX + 10) + 'px';
  tooltip.style.top = (event.pageY + 10) + 'px';
  tooltip.style.opacity = 1;
}

function hideTooltip() {
  const tooltip = document.getElementById('tooltip');
  tooltip.style.opacity = 0;
}

// Handles submission of the supply request form.
function handleSupplyRequest(event) {
  event.preventDefault();
  const itemTypeInput = document.getElementById('item-type');
  const itemType = itemTypeInput.value;
  if (itemType.trim() === '') {
    alert("Please enter an item type for the supply request.");
    return;
  }

  // Construct the request payload
  const payload = { item_type: itemType };

  // Post the supply request to the API endpoint.
  // (Ensure that your backend provides an /api/supply_request endpoint.)
  fetch('/api/supply_request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        alert("Supply request submitted successfully!");
        itemTypeInput.value = '';
        // Optionally, refresh logs after submitting a request.
        fetchLogs();
      } else {
        alert("Supply request failed. Try again.");
      }
    })
    .catch(error => {
      console.error("Error with supply request: ", error);
      alert("Error sending supply request.");
    });
}

// Fetches log data from the backend to display in the sidebar.
function fetchLogs() {
  fetch('/api/logs')
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        const logContainer = document.getElementById('log-container');
        logContainer.innerHTML = "";
        data.logs.forEach(log => {
          const entry = document.createElement('div');
          entry.classList.add('log-entry');
          entry.textContent = `[${log.timestamp}] [${log.action}]`;
          logContainer.appendChild(entry);
        });
      }
    })
    .catch(error => console.error("Error fetching logs: ", error));
}

