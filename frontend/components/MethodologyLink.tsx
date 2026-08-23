import Link from "next/link";
import { METHODOLOGY_HREF, type MethodologyTopic } from "@/lib/explain";

type Props = {
  topic: MethodologyTopic;
  children?: React.ReactNode;
  className?: string;
};

/** Plain-English “what does this mean?” link into Methodology anchors. */
export default function MethodologyLink({ topic, children, className }: Props) {
  return (
    <Link href={METHODOLOGY_HREF[topic]} className={className ?? "meth-link"}>
      {children ?? "What does this mean?"}
    </Link>
  );
}
