document.addEventListener("DOMContentLoaded", function () {
    let map = L.map('map').setView([37.7749, -122.4194], 13);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    async function fetchBusData() {
        try {
            let response = await fetch("http://127.0.0.1:8000/bus-positions");
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            let data = await response.json();

            data.bus_positions.forEach(bus => {
                if (bus.latitude && bus.longitude) {
                    L.marker([bus.latitude, bus.longitude])
                        .addTo(map)
                        .bindPopup(`<b>${bus.bus_number}</b><br>Stop: ${bus.current_stop}`);
                }
            });
        } catch (error) {
            console.error("Error fetching bus data:", error);
        }
    }

    fetchBusData();
    setInterval(fetchBusData, 15000);

    // Check if Leaflet is loaded
    if (typeof L === 'undefined') {
        console.error('Leaflet library not loaded');
        document.getElementById('errorMessage').textContent = 'Map loading failed';
        document.getElementById('errorMessage').classList.remove('hidden');
    }
});
