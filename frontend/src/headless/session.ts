import {
  unavailableSessionProvider,
  type SessionProvider,
} from "../api/session";

declare global {
  interface Window {
    /** Set by an approved host bootstrap before the Headless entry module loads. */
    __PLANTNEXUS_APS_SESSION_PROVIDER__?: SessionProvider;
  }
}

export function resolveHeadlessSessionProvider(
  source: Pick<Window, "__PLANTNEXUS_APS_SESSION_PROVIDER__"> = window,
): SessionProvider {
  const provider = source.__PLANTNEXUS_APS_SESSION_PROVIDER__;
  return provider !== undefined && typeof provider.getAccessToken === "function"
    ? provider
    : unavailableSessionProvider;
}
