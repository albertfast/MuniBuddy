import React from 'react';
import { GoogleMap, useJsApiLoader, InfoWindow } from '@react-google-maps/api';
import { Box, CircularProgress, Typography, Paper } from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LocationOnIcon from '@mui/icons-material/LocationOn';

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
    height: "100%",
    width: "100%"
  };

  const handleMarkerClick = (marker) => {
    setSelectedMarker(marker);
  };

  const onLoad = React.useCallback((map) => {
    setMap(map);
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

    markersRef.current.forEach(marker => {
      if (marker) marker.map = null;
    });
    markersRef.current = [];

    markers.forEach(markerData => {
      try {
        // Create modern marker
        const markerElement = document.createElement('div');
        markerElement.className = 'advanced-marker';
        markerElement.style.cursor = 'pointer';

        // Create custom marker container
        const markerContainer = document.createElement('div');
        markerContainer.className = 'marker-container';
        
        // Stylish container for icon
        const iconContainer = document.createElement('div');
        iconContainer.className = 'marker-icon';
        
        // SVG icon (bus icon)
        const svgIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svgIcon.setAttribute('viewBox', '0 0 24 24');
        svgIcon.setAttribute('width', '20');
        svgIcon.setAttribute('height', '20');
        svgIcon.setAttribute('fill', 'white');
        
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M4 16c0 1.1.9 2 2 2h1v1c0 .55.45 1 1 1s1-.45 1-1v-1h6v1c0 .55.45 1 1 1s1-.45 1-1v-1h1c1.1 0 2-.9 2-2v-3H4v3zm11.5-11c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zm-7 0c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zm3.5 2.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zM16 0H8C4.5 0 4 4.5 4 4.5v5.5h2V5c0-.55.45-1 1-1h10c.55 0 1 .45 1 1v5h2V4.5S19.5 0 16 0z');
        
        svgIcon.appendChild(path);
        iconContainer.appendChild(svgIcon);
        
        // Add small label (optional)
        if (markerData.title) {
          const label = document.createElement('div');
          label.className = 'marker-label';
          
          // Show stop number if available
          const stopNumber = markerData.title.match(/\d+/);
          if (stopNumber) {
            label.textContent = `#${stopNumber[0]}`;
          } else {
            // Get first word of stop name
            label.textContent = markerData.title.split(' ')[0];
          }
          
          markerContainer.appendChild(label);
        }
        
        markerContainer.appendChild(iconContainer);
        markerElement.appendChild(markerContainer);

        const advancedMarker = new window.google.maps.marker.AdvancedMarkerElement({
          position: markerData.position,
          content: markerElement,
          map: map,
          title: markerData.title,
          zIndex: 1
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
    return <Box sx={{ p: 2 }}>Error loading map.</Box>;
  }

  if (!isLoaded) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '400px', width: '100%', borderRadius: 2, overflow: 'hidden', boxShadow: 2 }}>
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
          mapId: 'munibuddy_map',
          styles: [
            {
              featureType: "transit.station",
              elementType: "labels.icon",
              stylers: [{ visibility: "on" }]
            },
            {
              featureType: "poi",
              elementType: "labels.icon",
              stylers: [{ visibility: "off" }]
            },
            {
              featureType: "transit",
              elementType: "geometry",
              stylers: [{ color: "#e5e5e5" }]
            },
            {
              featureType: "transit.station",
              elementType: "geometry",
              stylers: [{ color: "#eeeeee" }]
            },
            {
              featureType: "water",
              elementType: "geometry",
              stylers: [{ color: "#c9c9c9" }]
            }
          ]
        }}
      >
        {selectedMarker && (
          <InfoWindow
            position={selectedMarker.position}
            onCloseClick={() => setSelectedMarker(null)}
          >
            <Paper elevation={0} sx={{ p: 1, maxWidth: 200 }}>
              <Typography variant="subtitle2" gutterBottom>{selectedMarker.title}</Typography>
              {selectedMarker.description && (
                <Typography variant="body2" color="text.secondary">
                  {selectedMarker.description}
                </Typography>
              )}
            </Paper>
          </InfoWindow>
        )}
      </GoogleMap>
    </Box>
  );
};

export default Map; 