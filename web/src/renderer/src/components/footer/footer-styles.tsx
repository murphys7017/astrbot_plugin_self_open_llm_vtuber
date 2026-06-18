import { SystemStyleObject } from '@chakra-ui/react';

interface FooterStyles {
  container: (isCollapsed: boolean) => SystemStyleObject
  toggleButton: SystemStyleObject
  actionButton: SystemStyleObject
  input: SystemStyleObject
  attachButton: SystemStyleObject
}

interface AIIndicatorStyles {
  container: SystemStyleObject
  text: SystemStyleObject
}

export const footerStyles: {
  footer: FooterStyles
  aiIndicator: AIIndicatorStyles
} = {
  footer: {
    container: (isCollapsed) => ({
      bg: isCollapsed ? 'transparent' : 'rgba(10, 10, 10, 0.88)',
      borderTop: isCollapsed ? 'none' : '1px solid',
      borderColor: 'var(--olv-border)',
      transform: isCollapsed ? 'translateY(calc(100% - 24px))' : 'translateY(0)',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      height: '100%',
      position: 'relative',
      overflow: isCollapsed ? 'visible' : 'hidden',
      pb: '3',
      pt: '1',
      backdropFilter: 'blur(18px)',
      boxShadow: isCollapsed ? 'none' : '0 -20px 60px rgba(0, 0, 0, 0.28)',
    }),
    toggleButton: {
      height: '24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      cursor: 'pointer',
      color: 'var(--olv-muted)',
      _hover: { color: 'var(--olv-text)', bg: 'rgba(255,255,255,0.05)' },
      bg: 'transparent',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    },
    actionButton: {
      borderRadius: '8px',
      width: '44px',
      height: '44px',
      minW: '44px',
      border: '1px solid',
      borderColor: 'var(--olv-border)',
      boxShadow: 'none',
      _hover: {
        transform: 'translateY(-1px)',
        borderColor: 'var(--olv-border-strong)',
      },
      _active: {
        transform: 'translateY(0)',
      },
    },
    input: {
      bg: '#111111',
      border: '1px solid',
      borderColor: 'var(--olv-border)',
      height: '72px',
      borderRadius: '8px',
      fontSize: '15px',
      pl: '12',
      pr: '4',
      color: 'var(--olv-text)',
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
      _placeholder: {
        color: 'var(--olv-subtle)',
      },
      _focus: {
        borderColor: 'var(--olv-border-strong)',
        bg: '#111111',
        outline: 'none',
        boxShadow: '0 0 0 1px rgba(255,255,255,0.12)',
      },
      _hover: {
        borderColor: 'var(--olv-border-strong)',
      },
      resize: 'none',
      minHeight: '72px',
      maxHeight: '72px',
      py: '0',
      display: 'flex',
      alignItems: 'center',
      paddingTop: '24px',
      lineHeight: '1.45',
    },
    attachButton: {
      position: 'absolute',
      left: '2',
      top: '50%',
      transform: 'translateY(-50%)',
      color: 'var(--olv-muted)',
      zIndex: 2,
      width: '36px',
      height: '36px',
      minW: '36px',
      borderRadius: '8px',
      _hover: {
        bg: 'rgba(255,255,255,0.06)',
        color: 'var(--olv-text)',
      },
    },
  },
  aiIndicator: {
    container: {
      bg: 'rgba(16, 185, 129, 0.12)',
      color: 'var(--olv-success)',
      width: '104px',
      height: '28px',
      borderRadius: '999px',
      border: '1px solid rgba(16, 185, 129, 0.28)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: 'none',
      overflow: 'hidden',
    },
    text: {
      fontSize: '11px',
      fontWeight: '600',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    },
  },
};
