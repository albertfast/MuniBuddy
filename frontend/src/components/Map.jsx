import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress, Typography } from '@mui/material';

const libraries = ['marker']; // 'marker' is essential for AdvancedMarkerElement
const DEFAULT_CENTER = { lat: 37.7749, lng: -122.4194 };
const DEFAULT_ZOOM = 15;

const Map = ({ center = DEFAULT_CENTER, markers = [], onMapClick, zoom = DEFAULT_ZOOM }) => {
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [map, setMap] = useState(null);
  const markersRef = useRef([]);
  const logoControlRef = useRef(null); // Ref for the logo control div

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  useEffect(() => {
    if (apiKey) {
        console.log("🧭 Google Maps API Key Present");
    } else {
        console.warn("⚠️ Google Maps API Key is MISSING!");
    }
  }, [apiKey]);

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey || '',
    libraries: libraries,
    mapIds: [import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'YOUR_FALLBACK_MAP_ID'] // Ensure your Map ID is in .env
  });

  const mapContainerStyle = {
    height: '100%',
    width: '100%',
  };

  const handleMarkerClick = useCallback((markerData) => {
    console.log("📍 Marker clicked:", markerData.title, markerData);
    setSelectedMarker(markerData);
  }, []);

  const onLoad = useCallback((mapInstance) => {
    console.log("✅ Google Map instance loaded");
    setMap(mapInstance);

    // Add Logo Control after map loads
    if (window.google && mapInstance && !logoControlRef.current) {
      const logoDiv = document.createElement('div');
      logoDiv.className = 'map-logo-control'; // Add class for styling
      
      const logoImg = document.createElement('img');
      logoImg.src = '/images/munibuddy-logo.png'; // Path to your logo in public/images
      logoImg.alt = 'MuniBuddy Logo';
      logoImg.style.height = '35px'; // Adjust size as needed
      logoImg.style.width = 'auto';
      logoImg.style.padding = '5px';
      // logoImg.style.backgroundColor = 'rgba(255,255,255,0.8)'; // Optional: slight background
      // logoImg.style.borderRadius = '4px';
      // logoImg.style.boxShadow = '0 1px 3px rgba(0,0,0,0.2)';


      logoDiv.appendChild(logoImg);
      
      // Check if TOP_LEFT is available, otherwise use a fallback
      const controlPosition = window.google.maps.ControlPosition.TOP_LEFT || 9; // 9 is TOP_LEFT
      
      // Ensure controls array exists for the position
      if (!mapInstance.controls[controlPosition]) {
        mapInstance.controls[controlPosition] = new window.google.maps.MVCArray();
      }
      mapInstance.controls[controlPosition].push(logoDiv);
      logoControlRef.current = logoDiv; // Store ref to prevent re-adding
      console.log("🗺️ MuniBuddy Logo added to map");
    }

  }, []); // No dependency on setMap needed

  const onUnmount = useCallback(() => {
    console.log("🧹 Map unmounted, clearing map instance state");
    setMap(null);
    // Logo control will be removed automatically when map is destroyed
    logoControlRef.current = null;
  }, []);

  useEffect(() => {
    if (!map) return;
    if (!window.google || !window.google.maps.marker) {
      console.error("❌ Map effect skipped: Google Maps marker library not loaded");
      return;
    }

    markersRef.current.forEach(markerInstance => markerInstance.map = null);
    markersRef.current = [];

    markers.forEach(markerData => {
      if (!markerData?.position?.lat || !markerData?.position?.lng) {
        console.warn("⚠️ Skipping marker due to invalid position:", markerData);
        return;
      }
      try {
        const markerElement = document.createElement('div');
        markerElement.className = 'custom-map-marker';
        markerElement.style.cursor = 'pointer';

        const markerImage = document.createElement('img');
        markerImage.src = markerData.icon?.url || '/images/default-marker-icon.png';
        markerImage.onerror = () => { markerImage.style.display = 'none'; console.error(`Failed to load marker icon: ${markerImage.src}`); };
        markerImage.style.width = `${markerData.icon?.scaledSize?.width || 32}px`;
        markerImage.style.height = `${markerData.icon?.scaledSize?.height || 32}px`;
        markerElement.appendChild(markerImage);

        const advancedMarker = new window.google.maps.marker.AdvancedMarkerElement({
          position: markerData.position,
          content: markerElement,
          map: map,
          title: markerData.title
        });

        advancedMarker.addListener('gmp-click', () => handleMarkerClick(markerData));
        markersRef.current.push(advancedMarker);
      } catch (error) {
        console.error("❌ Error creating marker:", markerData.title, error);
      }
    });

    return () => {
      markersRef.current.forEach(markerInstance => markerInstance.map = null);
      markersRef.current = [];
    };
  }, [map, markers, handleMarkerClick]);

  if (loadError) {
    console.error("❌ Google Maps API load error:", loadError);
    return (
      <Box sx={{ p: 3, border: '1px dashed red', textAlign: 'center', height: '100%', display:'flex', flexDirection:'column', justifyContent:'center', alignItems:'center' }}>
        <Typography color="error" variant="h6">Map Load Error</Typography>
        <Typography color="error" variant="body2" sx={{ mt: 1 }}>
          Could not load Google Maps. This might be due to an invalid or restricted API key,
          network issues, or incorrect Map ID configuration.
        </Typography>
        <Typography variant="caption" sx={{mt:1}}>Check browser console for details.</Typography>
      </Box>
    );
  }

  if (!isLoaded) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '300px' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading Map...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', width: '100%', position: 'relative', borderRadius: '8px', overflow: 'hidden' }}>
      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        zoom={zoom}
        center={center}
        onClick={onMapClick}
        onLoad={onLoad}
        onUnmount={onUnmount}
        options={{
          zoomControl: true,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: true,
          mapId: import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'YOUR_FALLBACK_MAP_ID',
          gestureHandling: 'cooperative' // Good for user experience
        }}
      >
        {selectedMarker && (
          <InfoWindow
            position={selectedMarker.position}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <Box sx={{ p: 0.5, maxWidth: 250 }}> {/* Adjust padding and maxWidth */}
              <Typography variant="subtitle1" component="h3" sx={{ fontWeight: 'medium', fontSize: '1rem', mb: 0.5 }}>
                  {selectedMarker.title}
              </Typography>
              {selectedMarker.stopId && selectedMarker.stopId !== 'user-location' && (
                <Typography variant="body2" sx={{ fontSize: '0.8rem', color: 'text.secondary'}}>
                    Stop ID: {selectedMarker.stopId.replace(/-(bart|muni|sf)-?\d*$/i, '')} {/* Clean up stop ID for display */}
                </Typography>
              )}
            </Box>
          </InfoWindow>
        )}
      </GoogleMap>
    </Box>
  );
};

export default Map;