import { useEffect, useRef, useState } from "react";

export type AsyncState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
};

export function useAsyncTask<T>(task: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const runIdRef = useRef(0);

  const run = async () => {
    const runId = ++runIdRef.current;
    try {
      setLoading(true);
      setData(null);
      setError(null);
      const result = await task();
      if (runId !== runIdRef.current) {
        return;
      }
      setData(result);
    } catch (err) {
      if (runId !== runIdRef.current) {
        return;
      }
      const message = err instanceof Error ? err.message : "Ocurrio un error inesperado.";
      setError(message);
    } finally {
      if (runId === runIdRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void run();
    return () => {
      runIdRef.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload: run };
}
