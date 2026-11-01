import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { App } from '@capacitor/app'
import { Capacitor } from '@capacitor/core'

/**
 * Capacitor's native back button swallows the event unconditionally once a
 * JS listener is registered -- without this, pressing back at the root
 * screen (no WebView history left) would do nothing at all, since the
 * plugin's default handler only calls webView.goBack() when canGoBack() is
 * true and never falls through to exiting the app.
 */
export function useAndroidBackButton() {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return

    const listenerPromise = App.addListener('backButton', ({ canGoBack }) => {
      if (location.pathname !== '/' && canGoBack) {
        navigate(-1)
      } else {
        App.exitApp()
      }
    })

    return () => {
      listenerPromise.then((listener) => listener.remove())
    }
  }, [location, navigate])
}
