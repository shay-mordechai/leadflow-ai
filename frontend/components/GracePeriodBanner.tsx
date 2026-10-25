'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

export const GracePeriodBanner: React.FC = () => {
  const [isActive, setIsActive] = useState(false);
  const [remainingTime, setRemainingTime] = useState<string | null>(null);

  useEffect(() => {
    // Event listener for the interceptor
    const handleAlert = (event: Event) => {
      const customEvent = event as CustomEvent;
      setIsActive(true);
      if (customEvent.detail?.remaining) {
        setRemainingTime(customEvent.detail.remaining);
      }
    };

    window.addEventListener('GracePeriodAlert', handleAlert);

    // Cleanup the listener on component unmount
    return () => {
      window.removeEventListener('GracePeriodAlert', handleAlert);
    };
  }, []);

  if (!isActive) return null;

  return (
    <div className="bg-red-600 px-4 py-3 shadow-md flex items-center justify-center gap-3 z-50 relative">
      <AlertTriangle className="h-5 w-5 text-white animate-pulse" />
      <p className="text-sm font-medium text-white">
        Payment Failed (התשלום נכשל). Your subscription is past due. 
        Please update your billing details immediately to prevent data redaction.
      </p>
      <a
        href="/dashboard/billing"
        className="ml-4 bg-white text-red-600 px-4 py-1.5 rounded-md text-sm font-bold hover:bg-gray-100 transition-colors"
      >
        Update Payment Method
      </a>
    </div>
  );
};
