
import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  Divider,
  Box,
  Collapse,
  CircularProgress,
  Stack,
  Chip,
  IconButton,
  Button
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';

const TransitInfo = ({ stops }) => {
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);

  const stopsArray = Object.entries(stops).map(([id, stop]) => ({
    id,
    ...stop
  }));

  const handleStopClick = async (stop) => {
    if (selectedStop?.id === stop.id) {
      setSelectedStop(null);
      setStopSchedule(null);
      return;
    }

    setSelectedStop(stop);
    setLoading(true);

    try {
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/api/stop-schedule/${stop.stop_id}`);
      setStopSchedule(response.data);
    } catch (error) {
      console.error('Error fetching stop schedule:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (timeStr) => {
    if (!timeStr || timeStr === 'Unknown') return 'Unknown';
    const date = new Date(timeStr);
    return isNaN(date) ? timeStr : date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status) => {
    if (!status) return 'default';
    if (status.toLowerCase().includes('late')) return 'error';
    if (status.toLowerCase().includes('early')) return 'warning';
    return 'success';
  };

  const renderStopInfo = (stop) => (
    <>
      <Stack direction="row" alignItems="center" spacing={1}>
        <LocationOnIcon color="primary" />
        <Typography variant="body1">
          {stop.stop_name} ({stop.distance_miles} miles)
        </Typography>
      </Stack>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 0.5 }}>
        <DirectionsBusIcon fontSize="small" />
        <Typography variant="body2">
          Stop ID: {stop.stop_id || stop.id}
        </Typography>
      </Stack>
    </>
  );

  const renderRouteInfo = (bus) => (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="body1" sx={{ fontWeight: 'medium' }}>
          Route {bus.route_number}
        </Typography>
        <Chip
          size="small"
          label={bus.status}
          color={getStatusColor(bus.status)}
        />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        ⏰ Arrival: {formatTime(bus.arrival_time)}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        🏁 Destination: {bus.destination}
      </Typography>
    </Box>
  );

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" component="div" gutterBottom>
          Nearby Transit Stops ({stopsArray.length})
        </Typography>
        <List>
          {stopsArray.map((stop, stopIndex) => (
            <React.Fragment key={stop.id}>
              <ListItemButton
                onClick={() => handleStopClick(stop)}
                selected={selectedStop?.id === stop.id}
              >
                <ListItemText
                  primary={renderStopInfo(stop)}
                />
                <IconButton
                  onClick={(e) => {
                    e.stopPropagation();
                    handleStopClick(stop);
                  }}
                  size="small"
                >
                  {selectedStop?.id === stop.id ? (
                    <ExpandLessIcon />
                  ) : (
                    <ExpandMoreIcon />
                  )}
                </IconButton>
              </ListItemButton>

              <Collapse in={selectedStop?.id === stop.id}>
                <Box sx={{ pl: 2, pr: 2, pb: 2 }}>
                  {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                      <CircularProgress />
                    </Box>
                  ) : stopSchedule ? (
                    <Box>
                      {stopSchedule.inbound && stopSchedule.inbound.length > 0 && (
                        <Box sx={{ mb: 2 }}>
                          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                            <ArrowDownwardIcon color="primary" fontSize="small" />
                            <Typography variant="subtitle2" color="primary">
                              Inbound Routes
                            </Typography>
                          </Stack>
                          <List dense>
                            {stopSchedule.inbound.map((bus, index) => (
                              <ListItem key={index}>
                                <ListItemText
                                  primary={renderRouteInfo(bus)}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Box>
                      )}

                      {stopSchedule.outbound && stopSchedule.outbound.length > 0 && (
                        <Box>
                          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                            <ArrowUpwardIcon color="primary" fontSize="small" />
                            <Typography variant="subtitle2" color="primary">
                              Outbound Routes
                            </Typography>
                          </Stack>
                          <List dense>
                            {stopSchedule.outbound.map((bus, index) => (
                              <ListItem key={index}>
                                <ListItemText
                                  primary={renderRouteInfo(bus)}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Box>
                      )}

                      {(!stopSchedule.inbound?.length && !stopSchedule.outbound?.length) && (
                        <Typography color="text.secondary">
                          No scheduled routes at this time.
                        </Typography>
                      )}
                      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                        <Button
                          startIcon={<RefreshIcon />}
                          onClick={() => handleStopClick(selectedStop)}
                          disabled={loading}
                          size="small"
                          variant="outlined"
                        >
                          Yenile
                        </Button>
                      </Box>
                    </Box>
                  ) : (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                      <CircularProgress />
                    </Box>
                  )}
                </Box>
              </Collapse>

              {stopIndex < stopsArray.length - 1 && <Divider />}
            </React.Fragment>
          ))}
        </List>
      </CardContent>
    </Card>
  );
};

export default TransitInfo;
