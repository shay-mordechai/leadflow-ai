import axios from 'axios';

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '/api',
});

// Intercept all responses from the backend
apiClient.interceptors.response.use(
  (response) => {
    // Read the custom headers injected by FastAPI
    const alertHeader = response.headers['x-subscription-alert'];
    const graceRemaining = response.headers['x-grace-period-remaining'];

    // Trigger the global alert if the grace period is active
    if (alertHeader === 'grace_period_active') {
      window.dispatchEvent(
        new CustomEvent('GracePeriodAlert', {
          detail: { remaining: graceRemaining },
        })
      );
    }

    return response;
  },
  (error) => {
    return Promise.reject(error);
  }
);
