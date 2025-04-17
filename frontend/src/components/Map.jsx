// src/components/Map.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress, Typography } from '@mui/material';

const libraries = ['marker'];
const DEFAULT_CENTER = { lat: 37.7749, lng: -122.4194 };
const DEFAULT_ZOOM = 15;

const Map = ({ center = DEFAULT_CENTER, markers = [], liveVehicleMarkers = [], onMapClick, zoom = DEFAULT_ZOOM }) => {
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [map, setMap] = useState(null);
  const markersRef = useRef([]);

  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey || '',
    libraries,
    mapIds: ['munibuddy_map']
  });

  const mapContainerStyle = {
    width: '100%',
    height: 'calc(100dvh - 250px)',
    maxHeight: '65vh'
  };

  const handleMarkerClick = useCallback((markerData) => {
    setSelectedMarker(markerData);
  }, []);

  const onLoad = useCallback((mapInstance) => setMap(mapInstance), []);
  const onUnmount = useCallback(() => setMap(null), []);

  const createMarkerElement = (iconUrl, size = 32) => {
    const container = document.createElement('div');
    container.className = 'custom-map-marker';
    container.style.cursor = 'pointer';

    const img = document.createElement('img');
    img.src = iconUrl;
    img.style.width = `${size}px`;
    img.style.height = `${size}px`;
    img.onerror = () => { img.style.display = 'none'; };

    container.appendChild(img);
    return container;
  };

  const renderMarkers = (list = [], defaultIcon = '/images/bus-marker-32.svg') => {
    list.forEach((markerData) => {
      if (!markerData?.position?.lat || !markerData?.position?.lng) return;

      const marker = new window.google.maps.marker.AdvancedMarkerElement({
        position: markerData.position,
        content: createMarkerElement(markerData.icon?.url || defaultIcon, markerData.icon?.scaledSize?.width || 32),
        map,
        title: markerData.title || markerData.route || 'Transit'
      });

      marker.addListener('gmp-click', () => handleMarkerClick(markerData));
      markersRef.current.push(marker);
    });
  };

  useEffect(() => {
    if (!map || !window.google?.maps?.marker) return;

    // Clear existing markers
    markersRef.current.forEach((m) => { m.map = null; });
    markersRef.current = [];

    // Render both static and live markers
    renderMarkers(markers, '/images/bus-stop-icon32.svg');
    renderMarkers(liveVehicleMarkers, '/images/bus-marker-32.svg');

    return () => {
      markersRef.current.forEach((m) => { m.map = null; });
      markersRef.current = [];
    };
  }, [map, markers, liveVehicleMarkers, handleMarkerClick]);

  if (loadError) {
    return <Box sx={{ p: 3 }}><Typography color="error">Error loading map</Typography></Box>;
  }

  if (!isLoaded) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 300 }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading Map...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', width: '100%' }}>
      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        zoom={zoom}
        center={center}
        onClick={onMapClick}
        onLoad={onLoad}
        onUnmount={onUnmount}
        options={{
          zoomControl: true,
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
            <Box sx={{ p: 1 }}>
              <Typography variant="subtitle1" fontWeight="medium">{selectedMarker.title}</Typography>
            </Box>
          </InfoWindow>
        )}
      </GoogleMap>
    </Box>
  );
};

export default Map;
