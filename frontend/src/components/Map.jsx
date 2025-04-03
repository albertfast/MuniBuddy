import React from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress } from '@mui/material';

const libraries = ['marker'];

const Map = ({ center = { lat: 37.7749, lng: -122.4194 }, markers, onMapClick, zoom = 16 }) => {
  const [selectedMarker, setSelectedMarker] = React.useState(null);
  const [map, setMap] = React.useState(null);
  const markersRef = React.useRef([]);

  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY,
    libraries,
    mapIds: ['munibuddy_map']
  });

  const mapStyles = {
    height: '100%',
    width: '100%'
  };

  const handleMarkerClick = (marker) => {
    setSelectedMarker(marker);
  };

  const onLoad = React.useCallback((mapInstance) => {
    setMap(mapInstance);
  }, []);

  const onUnmount = React.useCallback(() => {
    markersRef.current.forEach(marker => {
      if (marker) marker.map = null;
    });
    markersRef.current = [];
    setMap(null);
  }, []);

  React.useEffect(() => {
    if (!map || !window.google || !window.google.maps.marker) return;

    // Clear existing markers
    markersRef.current.forEach(marker => {
      if (marker) marker.map = null;
    });
    markersRef.current = [];

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
      } catch (error) {
        console.error('Error creating marker:', error);
      }
    });

    return () => {
      markersRef.current.forEach(marker => {
        if (marker) marker.map = null;
      });
      markersRef.current = [];
    };
  }, [map, markers]);

  if (loadError) {
    return <Box sx={{ p: 2 }}>An error occurred while loading the map.</Box>;
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
