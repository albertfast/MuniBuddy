import React from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress, Typography } from '@mui/material';

const libraries = ['marker'];

const Map = ({ center = { lat: 37.7749, lng: -122.4194 }, markers, onMapClick, zoom = 16 }) => {
  const [selectedMarker, setSelectedMarker] = React.useState(null);
  const [map, setMap] = React.useState(null);
  const markersRef = React.useRef([]);

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  // 🔍 DEBUG: Log API key presence
  console.log("🧭 Google Maps API Key Present:", !!apiKey);

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey,
    libraries,
    mapIds: ['munibuddy_map']
  });

  const mapStyles = {
    height: '100%',
    width: '100%'
  };

  const handleMarkerClick = (marker) => {
    console.log("📍 Marker clicked:", marker.title);
    setSelectedMarker(marker);
  };

  const onLoad = React.useCallback((mapInstance) => {
    console.log("✅ Google Map loaded");
    setMap(mapInstance);
  }, []);

  const onUnmount = React.useCallback(() => {
    console.log("🧹 Map unmounted, clearing markers");
    markersRef.current.forEach(marker => {
      if (marker) marker.map = null;
    });
    markersRef.current = [];
    setMap(null);
  }, []);

  React.useEffect(() => {
    if (!map) {
      console.warn("⚠️ Map is not initialized yet");
      return;
    }
    if (!window.google || !window.google.maps.marker) {
      console.error("❌ Google Maps marker library not loaded");
      return;
    }

    // Clear previous markers
    markersRef.current.forEach(marker => {
      if (marker) marker.map = null;
    });
    markersRef.current = [];

    // Create and display new markers
    markers.forEach(markerData => {
      try {
        const markerElement = document.createElement('div');
        markerElement.className = 'advanced-marker';
        markerElement.style.cursor = 'pointer';

        const markerImage = document.createElement('img');
        markerImage.src = markerData.icon.url;
        markerImage.style.width = `${markerData.icon.scaledSize.width}px`;
        markerImage.style.height = `${markerData.icon.scaledSize.height}px`;
        markerElement.appendChild(markerImage);

        const advancedMarker = new window.google.maps.marker.AdvancedMarkerElement({
          position: markerData.position,
          content: markerElement,
          map: map,
          title: markerData.title
        });

        advancedMarker.addListener('gmp-click', () => handleMarkerClick(markerData));
        markersRef.current.push(advancedMarker);

        console.log("📍 Marker added:", markerData.title);
      } catch (error) {
        console.error("❌ Error creating marker:", error);
      }
    });

    return () => {
      console.log("🧽 Cleaning up markers");
      markersRef.current.forEach(marker => {
        if (marker) marker.map = null;
      });
      markersRef.current = [];
    };
  }, [map, markers]);

  // 🛑 Load error handling
  if (loadError) {
    console.error("❌ Map load error:", loadError);
    return <Box sx={{ p: 2 }}><Typography color="error">An error occurred while loading the map.</Typography></Box>;
  }

  if (!isLoaded) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '400px', width: '100%' }}>
      <GoogleMap
        mapContainerStyle={mapStyles}
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
          mapId: 'munibuddy_map'
        }}
      >
        {selectedMarker && (
          <InfoWindow
            position={selectedMarker.position}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <div>
              <h3>{selectedMarker.title}</h3>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>
    </Box>
  );
};

export default Map;