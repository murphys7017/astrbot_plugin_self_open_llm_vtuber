import { css } from '@emotion/react';

const commonStyles = {
  scrollbar: {
    '&::-webkit-scrollbar': {
      width: '6px',
    },
    '&::-webkit-scrollbar-track': {
      background: 'transparent',
    },
    '&::-webkit-scrollbar-thumb': {
      background: 'rgba(255,255,255,0.18)',
      borderRadius: '999px',
      border: '2px solid transparent',
      backgroundClip: 'content-box',
    },
  },
  panel: {
    border: '1px solid',
    borderColor: 'var(--olv-border)',
    borderRadius: '8px',
    bg: 'var(--olv-panel-soft)',
  },
  title: {
    fontSize: '12px',
    fontWeight: '600',
    color: 'var(--olv-muted)',
    mb: 3,
    textTransform: 'uppercase',
    letterSpacing: '0',
  },
};

export const sidebarStyles = {
  sidebar: {
    container: (isCollapsed: boolean) => ({
      position: 'absolute' as const,
      left: 0,
      top: 0,
      height: '100%',
      width: '440px',
      bg: 'rgba(10, 10, 10, 0.96)',
      transform: isCollapsed
        ? 'translateX(calc(-100% + 24px))'
        : 'translateX(0)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: 3,
      overflow: isCollapsed ? 'visible' : 'hidden',
      pb: '3',
      borderRight: '1px solid',
      borderColor: 'var(--olv-border)',
      boxShadow: isCollapsed ? 'none' : 'var(--olv-shadow)',
      backdropFilter: 'blur(18px)',
    }),
    toggleButton: {
      position: 'absolute',
      right: 0,
      top: 0,
      width: '24px',
      height: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      color: 'var(--olv-muted)',
      _hover: { color: 'var(--olv-text)', bg: 'rgba(255,255,255,0.06)' },
      bg: 'rgba(10, 10, 10, 0.72)',
      borderLeft: '1px solid',
      borderColor: 'var(--olv-border)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      zIndex: 1,
    },
    content: {
      flex: 1,
      width: '100%',
      display: 'flex',
      flexDirection: 'column' as const,
      gap: 4,
      overflow: 'hidden',
    },
    header: {
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 1,
      px: 4,
      py: 3,
      borderBottom: '1px solid',
      borderColor: 'var(--olv-border)',
    },
    headerButton: {
      width: '36px',
      height: '36px',
      minW: '36px',
      p: 0,
      borderRadius: '8px',
      bg: 'transparent',
      color: 'var(--olv-muted)',
      border: '1px solid',
      borderColor: 'transparent',
      _hover: {
        bg: 'rgba(255,255,255,0.06)',
        borderColor: 'var(--olv-border)',
        color: 'var(--olv-text)',
      },
      _active: {
        bg: 'rgba(255,255,255,0.1)',
      },
    },
    menuContent: {
      bg: '#111111',
      color: 'var(--olv-text)',
      border: '1px solid',
      borderColor: 'var(--olv-border)',
      borderRadius: '8px',
      boxShadow: '0 18px 48px rgba(0,0,0,0.36)',
      p: 1,
    },
    menuItem: {
      borderRadius: '6px',
      fontSize: '13px',
      color: 'var(--olv-muted)',
      _hover: {
        bg: 'rgba(255,255,255,0.06)',
        color: 'var(--olv-text)',
      },
      _checked: {
        color: 'var(--olv-text)',
      },
    },
  },

  chatHistoryPanel: {
    container: {
      flex: 1,
      overflow: 'hidden',
      px: 3,
      display: 'flex',
      flexDirection: 'column',
    },
    title: commonStyles.title,
    messageList: {
      ...commonStyles.panel,
      p: 0,
      width: '100%',
      flex: 1,
      overflowY: 'auto',
      css: {
        ...commonStyles.scrollbar,
        scrollPaddingBottom: '1rem',
      },
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    },
  },

  systemLogPanel: {
    container: {
      width: '100%',
      overflow: 'hidden',
      px: 4,
      minH: '200px',
      marginTop: 'auto',
    },
    title: commonStyles.title,
    logList: {
      ...commonStyles.panel,
      p: 4,
      height: '200px',
      overflowY: 'auto',
      fontFamily: 'mono',
      css: commonStyles.scrollbar,
    },
    entry: {
      p: 2,
      borderRadius: '8px',
      _hover: {
        bg: 'rgba(255,255,255,0.05)',
      },
    },
  },

  chatBubble: {
    container: {
      display: 'flex',
      position: 'relative',
      _hover: {
        bg: 'rgba(255,255,255,0.05)',
      },
      py: 1,
      px: 2,
      borderRadius: '8px',
    },
    message: {
      maxW: '90%',
      bg: 'transparent',
      p: 2,
    },
    text: {
      fontSize: 'xs',
      color: 'var(--olv-text)',
    },
    dot: {
      position: 'absolute',
      w: '2',
      h: '2',
      borderRadius: 'full',
      bg: 'white',
      top: '2',
    },
  },

  cameraPanel: {
    container: {
      width: '97%',
      overflow: 'hidden',
      px: 4,
      minH: '240px',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 4,
    },
    title: commonStyles.title,
    videoContainer: {
      ...commonStyles.panel,
      width: '100%',
      height: '240px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      transition: 'all 0.2s',
    },
    video: {
      width: '100%',
      height: '100%',
      objectFit: 'cover' as const,
      transform: 'scaleX(-1)',
      borderRadius: '8px',
      display: 'block',
    } as const,
  },

  screenPanel: {
    container: {
      width: '97%',
      overflow: 'hidden',
      px: 4,
      minH: '240px',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 4,
    },
    title: commonStyles.title,
    screenContainer: {
      ...commonStyles.panel,
      width: '100%',
      height: '240px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      transition: 'all 0.2s',
    },
    video: {
      width: '100%',
      height: '100%',
      objectFit: 'cover' as const,
      borderRadius: '8px',
      display: 'block',
    } as const,
  },

  // Add Browser Panel Styles
  browserPanel: {
    container: {
      width: '97%',
      overflow: 'hidden',
      px: 4,
      minH: '240px',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      mb: 4,
    },
    title: commonStyles.title,
    browserContainer: {
      ...commonStyles.panel,
      width: '100%',
      height: '240px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      transition: 'all 0.2s',
      cursor: 'pointer',
      _hover: {
        bg: 'rgba(255,255,255,0.05)',
      },
    },
    iframe: {
      width: '100%',
      height: '100%',
      border: 'none',
      borderRadius: '8px',
    } as const,
  },

  bottomTab: {
    container: {
      width: '97%',
      px: 4,
      position: 'relative' as const,
      zIndex: 0,
    },
    tabs: {
      width: '100%',
      bg: 'var(--olv-panel-soft)',
      borderRadius: '8px',
      p: '1',
    },
    list: {
      borderBottom: 'none',
      gap: '1',
      p: '1',
      bg: 'var(--olv-panel-soft)',
      border: '1px solid',
      borderColor: 'var(--olv-border)',
      borderRadius: '8px',
    },
    trigger: {
      color: 'var(--olv-muted)',
      display: 'flex',
      alignItems: 'center',
      gap: 2,
      px: 3,
      py: 2,
      borderRadius: '6px',
      fontSize: '12px',
      fontWeight: '500',
      _hover: {
        color: 'var(--olv-text)',
        bg: 'rgba(255,255,255,0.06)',
      },
      _selected: {
        color: 'var(--olv-bg)',
        bg: 'var(--olv-text)',
      },
    },
  },

  // Add styles for the Tool Call Indicator
  toolCallIndicator: {
    container: {
      pl: '44px', // Indent to align with message content (avatar width + gap)
      my: '1', // Reduced vertical margin (e.g., 4px if theme space 1 = 4px)
      gap: 2,
      width: '100%',
      minHeight: '24px', // Ensure minimum height
      display: 'flex', // Ensure display is flex
      alignItems: 'center', // Keep vertical alignment
      justifyContent: 'center', // Center items horizontally
    },
    icon: {
      color: 'var(--olv-muted)',
      boxSize: '14px',
    },
    text: {
      fontSize: 'xs',
      color: 'var(--olv-muted)',
    },
    spinner: {
      size: 'xs',
      color: 'var(--olv-muted)',
      ml: 0,
    },
    completedIcon: {
      color: 'var(--olv-success)',
      boxSize: '14px',
      ml: 0,
    },
    errorIcon: {
      color: 'red.300',
      boxSize: '14px',
      ml: 0,
    },
  },
};

export const chatPanelStyles = css`
  .cs-message-list {
    background: transparent !important;
    padding: 14px 12px !important;
  }
  
  .cs-message {
    margin: 10px 0 !important;
  }

  .cs-message__content {
    background: rgba(255, 255, 255, 0.045) !important;
    border: 1px solid var(--olv-border) !important;
    border-radius: 8px !important;
    padding: 10px 12px !important;
    color: var(--olv-text) !important;
    font-size: 13px !important;
    line-height: 1.55 !important;
    margin-top: 4px !important;
    box-shadow: none !important;
  }

  .cs-message__text {
    padding: 8px 0 !important;
  }

  .cs-message--outgoing .cs-message__content {
    background: #ededed !important;
    border-color: #ededed !important;
    color: #0a0a0a !important;
  }

  .cs-chat-container {
    background: transparent !important;
    border: 1px solid var(--olv-border) !important;
    border-radius: 8px !important;
    padding: 0 !important;
  }

  .cs-main-container {
    border: none !important;
    background: transparent !important;
    width: calc(100% - 24px) !important;
    margin-left: 0 !important;
  }

  .cs-message__sender {
    position: absolute !important;
    top: 0 !important;
    left: 36px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    color: var(--olv-muted) !important;
  }

  .cs-message__content-wrapper {
    max-width: 80%;
    margin: 0 8px;
  }

  .cs-avatar {
    background-color: #111111 !important;
    border: 1px solid var(--olv-border-strong) !important;
    color: var(--olv-text) !important;
    width: 28px !important;
    height: 28px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    border-radius: 50% !important;
  }

  .cs-message--outgoing .cs-avatar {
    background-color: #ededed !important;
    color: #0a0a0a !important;
    border-color: #ededed !important;
  }

  .cs-message__header {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
  }
`;
