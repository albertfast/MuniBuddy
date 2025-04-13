import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress, Typography } from '@mui/material';

// --- Constants ---
/**
 * Google Maps libraries to load. 'marker' is required for AdvancedMarkerElement.
 * @type {string[]}
 */
const libraries = ['marker'];

/**
 * Default map center (San Francisco).
 * @type {google.maps.LatLngLiteral}
 */
const DEFAULT_CENTER = { lat: 37.7749, lng: -122.4194 };

/**
 * Default map zoom level.
 * @type {number}
 */
const DEFAULT_ZOOM = 15; // Adjusted default zoom slightly

// --- Component ---

/**
 * Renders a Google Map with custom markers and info windows.
 * @param {object} props - Component props.
 * @param {google.maps.LatLngLiteral} [props.center=DEFAULT_CENTER] - The center coordinates for the map.
 * @param {Array<object>} props.markers - An array of marker data objects to display.
 *   Each object should have: position {lat, lng}, title (string), icon {url, scaledSize {width, height}}.
 * @param {function} props.onMapClick - Callback function triggered when the map is clicked. Receives map click event.
 * @param {number} [props.zoom=DEFAULT_ZOOM] - The initial zoom level of the map.
 */
const Map = ({ center = DEFAULT_CENTER, markers = [], onMapClick, zoom = DEFAULT_ZOOM }) => {
  // --- State ---
  const [selectedMarker, setSelectedMarker] = useState(null); // Holds the data of the currently selected marker for InfoWindow
  const [map, setMap] = useState(null); // Holds the Google Map instance

  // --- Refs ---
  // Ref to keep track of the actual Google Maps marker objects created
  const markersRef = useRef([]);

  // --- Environment Variables ---
  // Retrieve Google Maps API Key from environment variables
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  // Log API key presence during development/debugging
  useEffect(() => {
    console.log("🧭 Google Maps API Key Present:", !!apiKey);
  }, [apiKey]); // Log only if apiKey changes (effectively once)

  // --- API Loading ---
  // Hook from @react-google-maps/api to load the Google Maps JavaScript API
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey || '', // Pass empty string if key is missing to potentially see different errors
    libraries: libraries,
    // mapIds is needed if using Cloud-based Maps Styling features
    mapIds: ['munibuddy_map'] // Ensure this Map ID exists in your Google Cloud project
  });

  // --- Styles ---
  // Style object for the map container
  const mapContainerStyle = {
    height: '100%',
    width: '100%',
  };

  // --- Callbacks ---
  /** Handles clicking on a map marker */
  const handleMarkerClick = useCallback((markerData) => {
    console.log("📍 Marker clicked:", markerData.title, markerData);
    setSelectedMarker(markerData); // Set the clicked marker data for InfoWindow
  }, []); // No dependencies, function identity is stable

  /** Callback executed when the map instance is loaded */
  const onLoad = useCallback((mapInstance) => {
    console.log("✅ Google Map instance loaded");
    setMap(mapInstance); // Store the map instance in state
  }, []); // setMap is stable, so no dependency needed

  /** Callback executed when the map component is unmounted */
  const onUnmount = useCallback(() => {
    console.log("🧹 Map unmounted, clearing map instance state");
    setMap(null); // Clear map instance from state
    // Note: Marker cleanup is handled by the useEffect cleanup function
  }, []); // No dependencies needed

  // --- Effects ---
  /** Effect to manage map markers when the map instance or marker data changes */
  useEffect(() => {
    // Guard clause: Exit if map isn't loaded yet
    if (!map) {
      // console.warn("⚠️ Map effect skipped: Map not initialized yet");
      return;
    }
    // Guard clause: Exit if the necessary marker library isn't loaded
    if (!window.google || !window.google.maps.marker) {
      console.error("❌ Map effect skipped: Google Maps marker library not loaded");
      return;
    }

    console.log("🔄 Updating markers...");

    // 1. Clear existing markers from the map and the ref
    markersRef.current.forEach(markerInstance => {
      // console.log("   🧹 Removing old marker:", markerInstance.title);
      markerInstance.map = null; // Remove marker from map
    });
    markersRef.current = []; // Clear the reference array

    // 2. Create and add new markers based on the 'markers' prop
    markers.forEach(markerData => {
      if (!markerData?.position?.lat || !markerData?.position?.lng) {
          console.warn("⚠️ Skipping marker due to invalid position:", markerData);
          return; // Skip if position is invalid
      }
      try {
        // Create the DOM element for the custom marker content
        const markerElement = document.createElement('div');
        // Assign a class for potential CSS styling
        markerElement.className = 'custom-map-marker'; // Use a more specific class name
        markerElement.style.cursor = 'pointer';

        // Create the image element for the icon
        const markerImage = document.createElement('img');
        markerImage.src = markerData.icon?.url || '/images/default-marker-icon.png'; // Provide a default icon
        // Basic error handling for image load
        markerImage.onerror = () => { markerImage.style.display = 'none'; console.error(`Failed to load marker icon: ${markerImage.src}`); };
        // Apply size from marker data
        markerImage.style.width = `${markerData.icon?.scaledSize?.width || 32}px`;
        markerImage.style.height = `${markerData.icon?.scaledSize?.height || 32}px`;
        markerElement.appendChild(markerImage);

        // Create the AdvancedMarkerElement instance
        const advancedMarker = new window.google.maps.marker.AdvancedMarkerElement({
          position: markerData.position,
          content: markerElement, // Set the custom DOM element
          map: map, // Add marker to the current map instance
          title: markerData.title // Tooltip text on hover
        });

        // Add click listener to the marker instance
        // 'gmp-click' is the correct event for AdvancedMarkerElement
        advancedMarker.addListener('gmp-click', () => handleMarkerClick(markerData));

        // Store the created marker instance in the ref for cleanup
        markersRef.current.push(advancedMarker);

        // console.log("   ➕ Marker added:", markerData.title);
      } catch (error) {
        console.error("❌ Error creating marker:", markerData.title, error);
        // Continue adding other markers even if one fails
      }
    });
    console.log(`✅ Markers updated: ${markersRef.current.length} added.`);

    // Cleanup function: This runs when the component unmounts OR before the effect runs again
    return () => {
      console.log("🧼 useEffect cleanup: Removing markers before next update or unmount");
      markersRef.current.forEach(markerInstance => {
        markerInstance.map = null; // Ensure removal from map
      });
      markersRef.current = []; // Clear the ref
    };
  }, [map, markers, handleMarkerClick]); // Dependencies: Re-run if map instance, markers array, or click handler changes

  // --- Render Logic ---

  // Render loading error state
  if (loadError) {
    console.error("❌ Google Maps API load error:", loadError);
    return (
      <Box sx={{ p: 3, border: '1px dashed red', textAlign: 'center' }}>
        <Typography color="error" variant="h6">Map Error</Typography>
        <Typography color="error" variant="body2">
          Could not load Google Maps. Please check the API key, network connection,
          and browser console for more details.
        </Typography>
        {/* Optionally show more specific error info from loadError */}
      </Box>
    );
  }

  // Render loading state while API is loading
  if (!isLoaded) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '300px' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading Map...</Typography>
      </Box>
    );
  }

  // Render the map once loaded
  return (
    <Box sx={{ height: '100%', width: '100%', position: 'relative' }}>
      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        zoom={zoom}
        center={center}
        onClick={onMapClick} // Pass the click handler prop
        onLoad={onLoad} // Callback when map instance is ready
        onUnmount={onUnmount} // Callback when component unmounts
        options={{ // Map customization options
          zoomControl: true,
          mapTypeControl: false, // Hide map type (Satellite/Map) control
          streetViewControl: false, // Hide Street View Pegman control
          fullscreenControl: true, // Show fullscreen button
          mapId: 'munibuddy_map' // Link to Cloud-based map style (ensure ID is correct)
          // gestureHandling: 'cooperative' // Recommended to prevent accidental scroll hijacking
        }}
      >
        {/* Render InfoWindow when a marker is selected */}
        {selectedMarker && (
          <InfoWindow
            position={selectedMarker.position} // Position the InfoWindow at the marker's location
            onCloseClick={() => setSelectedMarker(null)} // Callback to close the InfoWindow
          >
            {/* Content inside the InfoWindow */}
            <Box sx={{ p: 1 }}>
              <Typography variant="subtitle1" component="h3" fontWeight="medium">
                  {selectedMarker.title}
              </Typography>
              {/* Add more details here if needed, e.g., stop ID */}
              {/* <Typography variant="body2">Stop ID: {selectedMarker.stopId}</Typography> */}
            </Box>
          </InfoWindow>
        )}
      </GoogleMap>
    </Box>
  );
};

export default Map;