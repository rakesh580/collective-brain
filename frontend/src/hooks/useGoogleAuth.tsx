import { createContext, useContext } from "react";

export const GoogleAuthEnabledContext = createContext(false);

export function useGoogleAuthEnabled() {
  return useContext(GoogleAuthEnabledContext);
}
