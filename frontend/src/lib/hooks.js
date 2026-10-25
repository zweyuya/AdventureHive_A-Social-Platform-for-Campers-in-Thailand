import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

/** Load an API path; returns {data, error, loading, reload}. Pass null to skip. */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: !!path });
  const load = useCallback(async () => {
    if (!path) return setState({ data: null, error: null, loading: false });
    setState((s) => ({ ...s, loading: true }));
    try {
      setState({ data: await api(path), error: null, loading: false });
    } catch (error) {
      setState({ data: null, error, loading: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}
