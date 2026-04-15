import { createContext, useContext } from "react";

const GoogleClientIdContext = createContext<string>("");

export const GoogleClientIdProvider = GoogleClientIdContext.Provider;

export function useGoogleClientId(): string {
  return useContext(GoogleClientIdContext);
}
