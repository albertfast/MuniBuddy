import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Typography,
  CircularProgress,
  Box
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

  return (
    <Box>
      {stops.map((stop) => (
        <Accordion key={stop.id} defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">🚏 {stop.stop_name}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="textSecondary">
              Stop ID: {stop.id} — Distance: {stop.distance_miles} mi
            </Typography>

            {loadingStops.includes(stop.id) ? (
              <CircularProgress size={24} />
            ) : (
              <>
                {stopSchedules[stop.id]?.outbound?.length > 0 && (
                  <Box mt={2}>
                    <Typography variant="subtitle1">↗ Next Outbound Buses:</Typography>
                    {stopSchedules[stop.id].outbound.map((bus, index) => (
                      <Typography key={index}>
                        - Route {bus.route_number} → {bus.destination} @ {bus.arrival_time} ({bus.status})
                      </Typography>
                    ))}
                  </Box>
                )}

                {stopSchedules[stop.id]?.inbound?.length > 0 && (
                  <Box mt={2}>
                    <Typography variant="subtitle1">↙ Next Inbound Buses:</Typography>
                    {stopSchedules[stop.id].inbound.map((bus, index) => (
                      <Typography key={index}>
                        - Route {bus.route_number} → {bus.destination} @ {bus.arrival_time} ({bus.status})
                      </Typography>
                    ))}
                  </Box>
                )}

                {stopSchedules[stop.id]?.inbound?.length === 0 && stopSchedules[stop.id]?.outbound?.length === 0 && (
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
