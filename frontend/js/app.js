document.addEventListener("DOMContentLoaded", function () {
    const searchForm = document.getElementById("searchForm");
    
    searchForm.addEventListener("submit", function (event) {
        event.preventDefault();
        
        const currentLocation = document.getElementById("currentLocation").value;
        const destination = document.getElementById("destination").value;
        
        if (!currentLocation || !destination) {
            alert("Please enter both current location and destination.");
            return;
        }
        
        console.log("Searching for route from", currentLocation, "to", destination);
        
        fetchRoute(currentLocation, destination);
    });
});

async function fetchRoute(currentLocation, destination) {
    try {
        let response = await fetch(`http://127.0.0.1:8000/get-route-details?route_short_name=${currentLocation}-${destination}`);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        let data = await response.json();
        console.log("Route details:", data);
    } catch (error) {
        console.error("Error fetching route details:", error);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Input validation
    const validateAddress = (address) => {
        return address.trim().length > 0;
    };

    // Error handling for geolocation
    const handleLocationError = (error) => {
        const errorMsg = document.getElementById('errorMessage');
        switch(error.code) {
            case error.PERMISSION_DENIED:
                errorMsg.textContent = "Location access denied";
                break;
            case error.POSITION_UNAVAILABLE:
                errorMsg.textContent = "Location unavailable";
                break;
            case error.TIMEOUT:
                errorMsg.textContent = "Location request timed out";
                break;
        }
        errorMsg.classList.remove('hidden');
    };
});