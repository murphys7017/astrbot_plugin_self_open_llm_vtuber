const isElectron = window.api !== undefined;
export const settingStyles = {
  settingUI: {
    container: {
      width: '100%',
      height: '100%',
      p: 4,
      gap: 4,
      position: 'relative',
      overflowY: 'auto',
      css: {
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
    },
    header: {
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      gap: 1,
    },
    title: {
      ml: 4,
      fontSize: '15px',
      fontWeight: '600',
      color: 'var(--olv-text)',
    },
    tabs: {
      root: {
        width: '100%',
        variant: 'plain' as const,
        colorPalette: 'gray',
      },
      content: {},
      trigger: {
        color: 'var(--olv-muted)',
        borderRadius: '6px',
        fontSize: '13px',
        _selected: {
          color: 'var(--olv-text)',
          bg: 'rgba(255,255,255,0.06)',
        },
        _hover: {
          color: 'var(--olv-text)',
        },
      },
      list: {
        display: 'flex',
        justifyContent: 'flex-start',
        flexWrap: 'wrap' as const,
        width: '100%',
        borderBottom: '1px solid',
        borderColor: 'var(--olv-border)',
        mb: 4,
        pl: 0,
        gap: 2,
      },
    },
    footer: {
      width: '100%',
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 2,
      mt: 'auto',
      pt: 4,
      borderTop: '1px solid',
      borderColor: 'var(--olv-border)',
    },
    drawerContent: {
      bg: 'var(--olv-bg)',
      maxWidth: '440px',
      height: isElectron ? 'calc(100vh - 30px)' : '100vh',
      borderLeft: '1px solid',
      borderColor: 'var(--olv-border)',
      boxShadow: 'var(--olv-shadow)',
    },
    drawerHeader: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      width: '100%',
      position: 'relative',
      px: 6,
      py: 4,
    },
    drawerTitle: {
      color: 'var(--olv-text)',
      fontSize: '15px',
      fontWeight: 'semibold',
    },
    closeButton: {
      position: 'absolute',
      right: 1,
      top: 1,
      color: 'var(--olv-muted)',

    },
  },
  general: {
    container: {
      align: 'stretch',
      gap: 6,
      p: 4,
    },
    field: {
      label: {
        color: 'var(--olv-muted)',
      },
    },
    select: {
      root: {
        colorPalette: 'gray',
        bg: '#111111',
      },
      trigger: {
        bg: '#111111',
        borderColor: 'var(--olv-border)',
      },
    },
    input: {
      bg: '#111111',
      borderColor: 'var(--olv-border)',
    },
    buttonGroup: {
      gap: 4,
      width: '100%',
    },
    button: {
      width: '50%',
      variant: 'outline' as const,
      bg: '#ededed',
      color: '#0a0a0a',
      borderColor: '#ededed',
      _hover: {
        bg: '#ffffff',
      },
    },
    fieldLabel: {
      fontSize: '14px',
      color: 'var(--olv-muted)',
    },
  },
  common: {
    field: {
      orientation: 'horizontal' as const,
    },
    fieldLabel: {
      fontSize: 'sm',
      color: 'var(--olv-muted)',
      whiteSpace: 'nowrap' as const,
    },
    switch: {
      size: 'md' as const,
      colorPalette: 'gray' as const,
      variant: 'solid' as const,
    },
    numberInput: {
      root: {
        pattern: '[0-9]*\\.?[0-9]*',
        inputMode: 'decimal' as const,
      },
      input: {
        bg: '#111111',
        borderColor: 'var(--olv-border)',
        _hover: {
          borderColor: 'var(--olv-border-strong)',
        },
      },
    },
    container: {
      gap: 8,
      maxW: 'sm',
      css: { '--field-label-width': '120px' },
    },
    input: {
      bg: '#111111',
      borderColor: 'var(--olv-border)',
      _hover: {
        borderColor: 'var(--olv-border-strong)',
      },
    },
  },
  live2d: {
    container: {
      gap: 8,
      maxW: 'sm',
      css: { '--field-label-width': '120px' },
    },
    statusText: {
      mt: -4,
      fontSize: '12px',
      color: 'var(--olv-muted)',
      lineHeight: 1.5,
    },
    emotionMap: {
      title: {
        fontWeight: 'bold',
        mb: 4,
      },
      entry: {
        mb: 2,
      },
      button: {
        colorPalette: 'gray',
        mt: 2,
      },
      deleteButton: {
        colorPalette: 'red',
      },
    },
  },
};
