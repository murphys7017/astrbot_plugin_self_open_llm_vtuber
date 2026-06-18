/* eslint-disable */
import { Box, Text } from "@chakra-ui/react";
import { FiMonitor } from "react-icons/fi";
import { useTranslation } from "react-i18next";
import { Tooltip } from "@/components/ui/tooltip";
import { sidebarStyles } from "./sidebar-styles";
import { useCaptureScreen } from "@/hooks/sidebar/use-capture-screen";

// Reusable components
function ScreenIndicator() {
  const { t } = useTranslation();
  
  return (
    <Box color="var(--olv-danger)" display="flex" alignItems="center" gap={2}>
      <Box
        w="7px"
        h="7px"
        borderRadius="full"
        bg="var(--olv-danger)"
        animation="pulse 2s infinite"
      />
      <Text fontSize="12px" fontWeight="600">{t('sidebar.screen')}</Text>
    </Box>
  );
}

function ScreenPlaceholder() {
  const { t } = useTranslation();
  
  return (
    <Box
      position="absolute"
      display="flex"
      flexDirection="column"
      alignItems="center"
      gap={2}
    >
      <FiMonitor size={24} />
      <Text color="var(--olv-muted)" fontSize="13px" textAlign="center">
        {t('footer.screenControl')}
      </Text>
    </Box>
  );
}

function VideoStream({
  videoRef,
  isStreaming,
}: {
  videoRef: React.RefObject<HTMLVideoElement>;
  isStreaming: boolean;
}) {
  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      style={sidebarStyles.screenPanel.video}
      {...(isStreaming ? {} : { display: "none" })}
    />
  );
}

function ScreenPanel(): JSX.Element {
  const { t } = useTranslation();
  const {
    videoRef,
    error,
    isHovering,
    isStreaming,
    toggleCapture,
    handleMouseEnter,
    handleMouseLeave,
  } = useCaptureScreen();

  return (
    <Box {...sidebarStyles.screenPanel.container}>
      <Box {...sidebarStyles.screenPanel.header}>
        {isStreaming && <ScreenIndicator />}
      </Box>

      <Tooltip
        showArrow
        content={
          isStreaming
            ? t('footer.screenStopping')
            : t('footer.screenControl')
        }
        open={isHovering && !error}
      >
        <Box
          {...sidebarStyles.screenPanel.screenContainer}
          onClick={toggleCapture}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          cursor="pointer"
          position="relative"
          _hover={{
            bg: "rgba(255,255,255,0.05)",
          }}
        >
          {error ? (
            <Text color="var(--olv-danger)" fontSize="13px" textAlign="center">
              {error}
            </Text>
          ) : (
            <>
              <VideoStream videoRef={videoRef} isStreaming={isStreaming} />
              {!isStreaming && <ScreenPlaceholder />}
            </>
          )}
        </Box>
      </Tooltip>
    </Box>
  );
}

export default ScreenPanel;
