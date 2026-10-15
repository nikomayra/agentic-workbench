import * as Tooltip from "@radix-ui/react-tooltip";
import { CircleHelp } from "lucide-react";
import type { ReactNode } from "react";

type InfoTooltipProps = {
  children: ReactNode;
  label?: string;
};

const InfoTooltip = ({
  children,
  label = "More information",
}: InfoTooltipProps): ReactNode => (
  <Tooltip.Provider delayDuration={250}>
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          aria-label={label}
          className="inline-flex rounded-full text-copy-muted transition hover:text-copy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400"
        >
          <CircleHelp aria-hidden="true" className="size-3.5" />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          sideOffset={6}
          className="z-50 max-w-72 rounded-md border border-line bg-zinc-900 px-3 py-2 text-xs leading-5 text-copy shadow-xl"
        >
          {children}
          <Tooltip.Arrow className="fill-zinc-900" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  </Tooltip.Provider>
);

export default InfoTooltip;
