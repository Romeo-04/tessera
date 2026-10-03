import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { forgetList, loadList, saveList, type SavedList } from "../lib/store";
import type { Drug } from "../lib/types";

interface Saved {
  saved: SavedList | null;
  loaded: boolean;
  save: (drugs: Drug[], incomplete: string[]) => Promise<void>;
  forget: () => Promise<void>;
}

const Ctx = createContext<Saved | null>(null);

export function useSaved(): Saved {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSaved outside SavedProvider");
  return s;
}

export function SavedProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<SavedList | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    loadList(AsyncStorage).then((l) => { setSaved(l); setLoaded(true); });
  }, []);

  const save = useCallback(async (drugs: Drug[], incomplete: string[]) => {
    await saveList(drugs, AsyncStorage, new Date(), incomplete);
    setSaved(await loadList(AsyncStorage));
  }, []);

  const forget = useCallback(async () => {
    await forgetList(AsyncStorage);
    setSaved(null);
  }, []);

  const value = useMemo(() => ({ saved, loaded, save, forget }), [saved, loaded, save, forget]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Same set of codes, regardless of order. */
export function sameList(a: Drug[], b: Drug[]): boolean {
  const ca = a.map((d) => d.rxcui).filter(Boolean).sort().join(",");
  const cb = b.map((d) => d.rxcui).filter(Boolean).sort().join(",");
  return ca.length > 0 && ca === cb;
}
