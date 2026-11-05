import { useCallback, useEffect, useState } from 'react';
import type { NetworkStatus } from '../services/sessionService';

function readNetworkStatus(): NetworkStatus {
  return typeof navigator === 'undefined' || navigator.onLine ? 'online' : 'offline';
}

/**
 * Tracks browser connectivity and mirrors changes into the session store.
 */
export function useNetworkStatus(onStatusChange: (status: NetworkStatus) => void): Readonly<{
  networkStatus: NetworkStatus;
  setNetworkStatus(status: NetworkStatus): void;
}> {
  const [networkStatus, setNetworkStatus] = useState<NetworkStatus>(readNetworkStatus);

  const updateNetworkStatus = useCallback(
    (status: NetworkStatus): void => {
      onStatusChange(status);
      setNetworkStatus(status);
    },
    [onStatusChange],
  );

  useEffect(() => {
    function handleOnline(): void {
      updateNetworkStatus('online');
    }

    function handleOffline(): void {
      updateNetworkStatus('offline');
    }

    updateNetworkStatus(readNetworkStatus());
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [updateNetworkStatus]);

  return { networkStatus, setNetworkStatus: updateNetworkStatus };
}
