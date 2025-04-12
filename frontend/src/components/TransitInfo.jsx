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

  // Convert stops object to array
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
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/api/stop-schedule/${stop.id}`);
      setStopSchedule(response.data);
    } catch (error) {
      console.error('Error fetching stop schedule:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (isoTime) => {
    if (!isoTime || isoTime === "Unknown") return "Unknown";
    
    // If time format is like '12:34 AM', it's already formatted, return directly
    if (/\d{1,2}:\d{2}\s[AP]M/.test(isoTime)) {
      return isoTime;
    }
    
    try {
      const date = new Date(isoTime);
      // Check if date is valid
      if (isNaN(date.getTime())) {
        // If not ISO format, it's probably already a formatted string
        return isoTime;
      }
      
      return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit'
      });
    } catch (error) {
      console.error('Date parsing error:', error, 'Value:', isoTime);
      return isoTime; // Return original value in case of error
    }
  };

  const getStatusColor = (status) => {
    if (status.includes('late')) return 'error';
    if (status === 'Early') return 'warning';
    return 'success';
  };

  const renderStopInfo = (stop) => (
    <>
      <Stack direction="row" alignItems="center" spacing={1}>
        <LocationOnIcon color="primary" sx={{ color: '#1976d2' }} />
        <Typography variant="body1" sx={{ fontWeight: 500 }}>
          {stop.stop_name}
        </Typography>
      </Stack>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mt: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <DirectionsBusIcon fontSize="small" sx={{ color: '#757575', mr: 0.5 }} />
          <Typography variant="body2" color="text.secondary">
            Stop ID: {stop.id}
          </Typography>
        </Box>
        <Chip 
          size="small" 
          label={`${stop.distance_miles} miles`} 
          sx={{ 
            height: '20px', 
            fontSize: '0.7rem',
            bgcolor: 'rgba(25, 118, 210, 0.08)',
            color: 'primary.main'
          }} 
        />
      </Stack>
    </>
  );

  const renderRouteInfo = (route) => (
    <Box sx={{ borderLeft: '3px solid #1976d2', pl: 1, py: 0.5, mb: 1 }}>
      <Stack direction="row" alignItems="center" spacing={1} justifyContent="space-between">
        <Typography variant="body1" sx={{ fontWeight: 'medium', color: '#1976d2' }}>
          {route.route_number} → {route.destination}
        </Typography>
        <Chip 
          size="small"
          label={route.status}
          color={getStatusColor(route.status)}
          sx={{ 
            height: '22px', 
            fontSize: '0.7rem',
            '& .MuiChip-label': { px: 1 }
          }}
        />
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center' }}>
          Arrival: <Box component="span" sx={{ fontWeight: 'bold', ml: 0.5 }}>{formatTime(route.arrival_time)}</Box>
          {route.stops_away && ` • ${route.stops_away} stops away`}
        </Box>
      </Typography>
    </Box>
  );

  return (
    <Card elevation={2} sx={{ borderRadius: 2, overflow: 'hidden' }}>
      <CardContent sx={{ pb: 1 }}>
        <Typography variant="h6" component="div" gutterBottom sx={{ fontWeight: 'bold', color: '#1976d2' }}>
          Nearby Stops ({stopsArray.length})
        </Typography>
        <List sx={{ mt: 1 }}>
          {stopsArray.map((stop, stopIndex) => (
            <React.Fragment key={stop.id}>
              <ListItemButton 
                onClick={() => handleStopClick(stop)}
                selected={selectedStop?.id === stop.id}
                sx={{ 
                  borderRadius: 1,
                  mb: 0.5,
                  '&.Mui-selected': {
                    backgroundColor: 'rgba(25, 118, 210, 0.08)',
                  },
                  '&:hover': {
                    backgroundColor: 'rgba(25, 118, 210, 0.04)',
                  }
                }}
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
                  sx={{ 
                    backgroundColor: selectedStop?.id === stop.id ? 'rgba(25, 118, 210, 0.12)' : 'transparent',
                    '&:hover': {
                      backgroundColor: 'rgba(25, 118, 210, 0.18)',
                    }
                  }}
                >
                  {selectedStop?.id === stop.id ? (
                    <ExpandLessIcon fontSize="small" />
                  ) : (
                    <ExpandMoreIcon fontSize="small" />
                  )}
                </IconButton>
              </ListItemButton>

              <Collapse in={selectedStop?.id === stop.id}>
                <Box sx={{ pl: 2, pr: 2, pb: 2 }}>
                  {loading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                      <CircularProgress size={28} />
                    </Box>
                  ) : stopSchedule ? (
                    <Box>
                      {stopSchedule.inbound && stopSchedule.inbound.length > 0 && (
                        <Box sx={{ mb: 2 }}>
                          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                            <ArrowDownwardIcon color="primary" fontSize="small" />
                            <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 'bold' }}>
                              Inbound Routes
                            </Typography>
                          </Stack>
                          <List dense sx={{ pl: 1 }}>
                            {stopSchedule.inbound.map((route, index) => (
                              <ListItem key={index} sx={{ px: 0 }}>
                                <ListItemText
                                  primary={renderRouteInfo(route)}
                                  disableTypography
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
                            <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 'bold' }}>
                              Outbound Routes
                            </Typography>
                          </Stack>
                          <List dense sx={{ pl: 1 }}>
                            {stopSchedule.outbound.map((route, index) => (
                              <ListItem key={index} sx={{ px: 0 }}>
                                <ListItemText
                                  primary={renderRouteInfo(route)}
                                  disableTypography
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Box>
                      )}

                      {(!stopSchedule.inbound?.length && !stopSchedule.outbound?.length) && (
                        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
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
                          sx={{ 
                            borderRadius: '20px',
                            textTransform: 'none',
                            px: 2
                          }}
                        >
                          Refresh
                        </Button>
                      </Box>
                    </Box>
                  ) : (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
                      <CircularProgress size={28} />
                    </Box>
                  )}
                </Box>
              </Collapse>

              {stopIndex < stopsArray.length - 1 && <Divider sx={{ my: 0.5 }} />}
            </React.Fragment>
          ))}
        </List>
      </CardContent>
    </Card>
  );
};

export default TransitInfo; 