import { useEffect, useState } from "react";

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

  const run = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await task();
      setData(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Ocurrio un error inesperado.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload: run };
}
