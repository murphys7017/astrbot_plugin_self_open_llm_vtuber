import { useEffect } from 'react';
import { Box, Text } from '@chakra-ui/react';
import { FiCamera } from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import { Tooltip } from '@/components/ui/tooltip';
import { sidebarStyles } from './sidebar-styles';
import { useCameraPanel } from '@/hooks/sidebar/use-camera-panel';

// Reusable components
function LiveIndicator() {
  const { t } = useTranslation();

  return (
    <Box color="var(--olv-danger)" display="flex" alignItems="center" gap={2}>
      <Box w="7px" h="7px" borderRadius="full" bg="var(--olv-danger)" animation="pulse 2s infinite" />
      <Text fontSize="12px" fontWeight="600">{t('sidebar.live')}</Text>
    </Box>
  );
}

function CameraPlaceholder() {
  const { t } = useTranslation();

  return (
    <Box
      position="absolute"
      display="flex"
      flexDirection="column"
      alignItems="center"
      gap={2}
    >
      <FiCamera size={24} />
      <Text color="var(--olv-muted)" fontSize="13px" textAlign="center">
        {t('footer.cameraControl')}
      </Text>
    </Box>
  );
}

function VideoStream({
  videoRef,
  isStreaming,
}: {
  videoRef: React.RefObject<HTMLVideoElement>
  isStreaming: boolean
}) {
  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      style={sidebarStyles.cameraPanel.video}
      {...(isStreaming ? {} : { display: 'none' })}
    />
  );
}

// Main component
function CameraPanel(): JSX.Element {
  const { t } = useTranslation();
  const {
    videoRef,
    error,
    isHovering,
    isStreaming,
    stream,
    toggleCamera,
    handleMouseEnter,
    handleMouseLeave,
  } = useCameraPanel();

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <Box {...sidebarStyles.cameraPanel.container}>
      <Box {...sidebarStyles.cameraPanel.header}>
        {isStreaming && <LiveIndicator />}
      </Box>

      <Tooltip
        showArrow
        content={isStreaming ? t('footer.cameraStopping') : t('footer.cameraControl')}
        open={isHovering && !error}
      >
        <Box
          {...sidebarStyles.cameraPanel.videoContainer}
          onClick={toggleCamera}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          cursor="pointer"
          position="relative"
          _hover={{
            bg: 'rgba(255,255,255,0.05)',
          }}
        >
          {error ? (
            <Text color="var(--olv-danger)" fontSize="13px" textAlign="center">
              {error}
            </Text>
          ) : (
            <>
              <VideoStream videoRef={videoRef} isStreaming={isStreaming} />
              {!isStreaming && <CameraPlaceholder />}
            </>
          )}
        </Box>
      </Tooltip>
    </Box>
  );
}

export default CameraPanel;
