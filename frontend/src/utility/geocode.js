/**
 * Geocoding utility functions for MuniBuddy
 */

/**
 * Geocodes an address string to coordinates using Google Maps API
 * @param {string} address - The address to geocode
 * @returns {Promise<{lat: number, lng: number, display_name: string}>}
 */
export const geocodeAddress = async (address) => {
  return new Promise((resolve, reject) => {
    // Check if Google Maps API is loaded
    if (!window.google || !window.google.maps) {
      reject(new Error("Google Maps API not loaded"));
      return;
    }

    const geocoder = new window.google.maps.Geocoder();
    
    geocoder.geocode({ address }, (results, status) => {
      if (status === "OK" && results && results[0]) {
        const location = results[0].geometry.location;
        resolve({
          lat: location.lat(),
          lng: location.lng(),
          display_name: results[0].formatted_address
        });
      } else {
        reject(new Error(`Geocoding failed: ${status}`));
      }
    });
  });
};

/**
 * Parses a string to check if it contains valid coordinates
 * @param {string} input - String to check for coordinates
 * @returns {null|{lat: number, lng: number}} Coordinates or null if invalid
 */
export const parseCoordinates = (input) => {
  if (!input) return null;
  
  const coordsMatch = input.match(/^(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)$/);
  
  if (coordsMatch) {
    const lat = parseFloat(coordsMatch[1]);
    const lng = parseFloat(coordsMatch[3]);
    
    if (!isNaN(lat) && !isNaN(lng)) {
      return { lat, lng };
    }
  }
  
  return null;
};

/**
 * Formats coordinates as a string
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @param {number} precision - Decimal precision (default: 5)
 * @returns {string} Formatted coordinates string
 */
export const formatCoordinates = (lat, lng, precision = 5) => {
  return `${lat.toFixed(precision)}, ${lng.toFixed(precision)}`;
};

// Remove handleManualLocationSearch from this file - it belongs in your App.jsx