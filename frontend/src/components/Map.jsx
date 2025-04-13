import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress, Typography } from '@mui/material';

const libraries = ['marker'];
const DEFAULT_CENTER = { lat: 37.7749, lng: -122.4194 };
const DEFAULT_ZOOM = 15;

const Map = ({ center = DEFAULT_CENTER, markers = [], onMapClick, zoom = DEFAULT_ZOOM }) => {
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [map, setMap] = useState(null);
  const markersRef = useRef([]);
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  useEffect(() => {
    console.log("🧭 Google Maps API Key Present:", !!apiKey);
  }, [apiKey]);

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: apiKey || '',
    libraries,
    mapIds: ['munibuddy_map']
  });

  const mapContainerStyle = {
    height: '100%',
    width: '100%',
    minHeight: '300px'
  };

  const mapOptions = {
    gestureHandling: 'greedy',
    zoomControl: true,
    fullscreenControl: false,
    streetViewControl: false,
    mapTypeControl: false
  };

  const handleMarkerClick = useCallback((markerData) => {
    console.log("📍 Marker clicked:", markerData.title, markerData);
    setSelectedMarker(markerData);
    if (map) {
      map.panTo(markerData.position);
      map.setZoom(isMobile ? 16 : 17);
    }
  }, [map, isMobile]);

  const onLoad = useCallback((mapInstance) => {
    console.log("✅ Google Map instance loaded");
    setMap(mapInstance);
  }, []);

  const onUnmount = useCallback(() => {
    console.log("🧹 Map unmounted, clearing map instance state");
    setMap(null);
  }, []);

  // 🔁 When center prop changes, pan the map to new location
  useEffect(() => {
    if (map && center) {
      map.panTo(center);
    }
  }, [map, center]);

  useEffect(() => {
    if (!map || !window.google || !window.google.maps.marker) return;

    console.log("🔄 Updating markers...");
    markersRef.current.forEach(markerInstance => markerInstance.map = null);
    markersRef.current = [];

    markers.forEach(markerData => {
      if (!markerData?.position?.lat || !markerData?.position?.lng) return;

      try {
        const markerElement = document.createElement('div');
        markerElement.className = 'custom-map-marker';
        markerElement.style.cursor = 'pointer';

        const markerImage = document.createElement('img');
        const size = isMobile ? 24 : 32;
        markerImage.src = markerData.icon?.url || '/images/default-marker-icon.png';
        markerImage.onerror = () => {
          markerImage.style.display = 'none';
          console.error(`Failed to load marker icon: ${markerImage.src}`);
        };
        markerImage.style.width = `${markerData.icon?.scaledSize?.width || size}px`;
        markerImage.style.height = `${markerData.icon?.scaledSize?.height || size}px`;
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
      console.log("🧼 useEffect cleanup: Removing markers before next update or unmount");
      markersRef.current.forEach(markerInstance => markerInstance.map = null);
      markersRef.current = [];
    };
  }, [map, markers, handleMarkerClick, isMobile]);

  if (loadError) {
    return (
      <Box sx={{ p: 3, border: '1px dashed red', textAlign: 'center' }}>
        <Typography color="error" variant="h6">Map Error</Typography>
        <Typography color="error" variant="body2">
          Could not load Google Maps. Please check the API key, network connection, and browser console.
        </Typography>
      </Box>
    );
  }

  if (!isLoaded) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading Map...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={mapContainerStyle}>
      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        center={center}
        zoom={zoom}
        onClick={onMapClick}
        options={mapOptions}
        onLoad={onLoad}
        onUnmount={onUnmount}
      >
        {selectedMarker && (
          <InfoWindow
            position={selectedMarker.position}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <div>
              <Typography variant="subtitle2">{selectedMarker.title}</Typography>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>
    </Box>
  );
};

export default Map;
