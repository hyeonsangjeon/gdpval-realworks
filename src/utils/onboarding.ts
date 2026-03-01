const STORAGE_PREFIX = 'gdpval-'

export const onboarding = {
  isAboutSeen: () => localStorage.getItem(`${STORAGE_PREFIX}about-seen`) === 'true',
  markAboutSeen: () => localStorage.setItem(`${STORAGE_PREFIX}about-seen`, 'true'),

  isHintDismissed: (tabId: string) =>
    localStorage.getItem(`${STORAGE_PREFIX}hint-${tabId}-dismissed`) === 'true',
  dismissHint: (tabId: string) =>
    localStorage.setItem(`${STORAGE_PREFIX}hint-${tabId}-dismissed`, 'true'),

  resetAll: () => {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(STORAGE_PREFIX))
      .forEach((k) => localStorage.removeItem(k))
  },
}
