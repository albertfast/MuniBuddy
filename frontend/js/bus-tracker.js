let updateInterval;
const MAX_RETRIES = 3;

const startAutoUpdate = () => {
    const statusElement = document.getElementById('updateStatus');
    let retryCount = 0;

    updateInterval = setInterval(async () => {
        try {
            const response = await fetchBusPositions();
            if (!response.ok && retryCount < MAX_RETRIES) {
                retryCount++;
                statusElement.textContent = `Retry ${retryCount}/${MAX_RETRIES}...`;
                return;
            }
            retryCount = 0;
            statusElement.textContent = 'Updated: ' + new Date().toLocaleTimeString();
        } catch (error) {
            console.error('Update failed:', error);
            statusElement.textContent = 'Update failed';
        }
    }, 30000); // 30-second interval
};