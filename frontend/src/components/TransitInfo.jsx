// Simplified TransitInfo component
// Displays real-time outbound schedule data only

import React, { useState } from 'react';
import {
  Card, CardContent, Typography, List, ListItem, ListItemText,
  CircularProgress, Chip, Box, Stack
} from '@mui/material';
import axios from 'axios';

const TransitInfo = ({ stops }) => {
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleStopClick = async (stop) => {
    if (selectedStop?.id === stop.id) {
      setSelectedStop(null);
      setStopSchedule(null);
      return;
    }

    setSelectedStop(stop);
    setLoading(true);

    try {
      const stopId = stop.id || stop.stop_id;
      const response = await axios.get(`${import.meta.env.VITE_API_BASE}/stop-schedule/${stopId}`);

      // Keep only outbound routes
      const outboundRoutes = response.data.outbound || [];
      setStopSchedule({ outbound: outboundRoutes });
    } catch (error) {
      console.error('Failed to fetch stop schedule:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (time) => {
    try {
      const date = new Date(time);
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return time;
    }
  };

  const stopsArray = Array.isArray(stops) ? stops : Object.values(stops || {});

  return (
    <Card>
      <CardContent>
        <Typography variant="h6">Outbound Stop Schedules</Typography>
        <List>
          {stopsArray.map((stop) => (
            <ListItem key={stop.id || stop.stop_id} button onClick={() => handleStopClick(stop)}>
              <ListItemText primary={stop.stop_name} secondary={`Stop ID: ${stop.id || stop.stop_id}`} />
            </ListItem>
          ))}
        </List>

        {loading && <CircularProgress size={28} />}

        {stopSchedule?.outbound?.length > 0 && (
          <Box mt={2}>
            <Typography variant="subtitle1">Outbound Routes</Typography>
            <List>
              {stopSchedule.outbound.map((route, index) => (
                <ListItem key={index}>
                  <ListItemText
                    primary={`${route.route_number} → ${route.destination}`}
                    secondary={`Arrival: ${formatTime(route.arrival_time)}${route.stops_away ? ` • ${route.stops_away} stops` : ''}`}
                  />
                  <Chip label={route.status} color="success" size="small" />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {!loading && selectedStop && (!stopSchedule || stopSchedule.outbound?.length === 0) && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            No outbound schedule found for this stop.
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default TransitInfo;
