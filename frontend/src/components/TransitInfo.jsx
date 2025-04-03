import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Typography,
  CircularProgress,
  Box,
  Chip,
  Divider,
  Stack
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

const TransitInfo = ({ stops }) => {
  const [stopSchedules, setStopSchedules] = useState({});
  const [loadingStops, setLoadingStops] = useState([]);

  useEffect(() => {
    const fetchSchedules = async () => {
      const schedules = {};
      const loading = [];

      for (const stop of stops) {
        loading.push(stop.id);
        try {
          const response = await axios.get(`${import.meta.env.VITE_API_URL}/api/stop-schedule/${stop.id}`);
          schedules[stop.id] = response.data;
        } catch (error) {
          console.error(`Error fetching schedule for stop ${stop.id}:`, error);
          schedules[stop.id] = { inbound: [], outbound: [] };
        }
      }

      setStopSchedules(schedules);
      setLoadingStops([]);
    };

    if (stops.length > 0) {
      fetchSchedules();
    }
  }, [stops]);

  const renderRouteDetails = (buses, label) => (
    <Box mt={2}>
      <Typography variant="subtitle1" gutterBottom>
        {label}
      </Typography>
      <Divider sx={{ mb: 1 }} />
      <Stack spacing={1}>
        {buses.map((bus, idx) => (
          <Box key={idx} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography>
              <strong>{bus.route_number}</strong> → {bus.destination}<br />
              Arrival: <strong>{bus.arrival_time}</strong>
            </Typography>
            <Chip label={bus.status} color={bus.status.includes('Delay') ? 'error' : 'success'} size="small" />
          </Box>
        ))}
      </Stack>
    </Box>
  );

  return (
    <Box>
      <Typography variant="h6" sx={{ mt: 2, mb: 2 }}>
        Nearby Stops ({stops.length})
      </Typography>

      {stops.map((stop) => (
        <Accordion key={stop.id} defaultExpanded={false}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                📍 {stop.stop_name}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                🚌 Stop ID: {stop.id} &nbsp;&nbsp; 📏 {stop.distance_miles.toFixed(2)} miles
              </Typography>
            </Box>
          </AccordionSummary>

          <AccordionDetails>
            {loadingStops.includes(stop.id) ? (
              <CircularProgress size={24} />
            ) : (
              <>
                {stopSchedules[stop.id]?.inbound?.length > 0 &&
                  renderRouteDetails(stopSchedules[stop.id].inbound, 'Inbound Routes')}

                {stopSchedules[stop.id]?.outbound?.length > 0 &&
                  renderRouteDetails(stopSchedules[stop.id].outbound, 'Outbound Routes')}

                {stopSchedules[stop.id]?.inbound?.length === 0 &&
                  stopSchedules[stop.id]?.outbound?.length === 0 && (
                    <Typography color="textSecondary">No upcoming buses for this stop.</Typography>
                )}
              </>
            )}
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
};

export default TransitInfo;
