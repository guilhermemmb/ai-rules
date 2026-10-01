import { Type } from "@earendil-works/pi-ai";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { executeReviewEvidenceTool } from "../review/command.mjs";

const reviewEvidenceTool = defineTool({
  name: "review_evidence",
  label: "Review evidence",
  description: "Prepare immutable evidence and bounded arguments for pi-review, or verify that a delivered review still matches its frozen repository/PR snapshot.",
  parameters: Type.Object({
    action: Type.Union([Type.Literal("prepare"), Type.Literal("verify")]),
    invocation: Type.Optional(Type.String({ description: "Complete /review argument text, treated only as scope data." })),
    packetRef: Type.Optional(Type.String({ description: "Absolute packet path returned by prepare." })),
  }, { additionalProperties: false }),
  annotations: {
    readOnlyHint: false,
    destructiveHint: false,
    idempotentHint: true,
    openWorldHint: true,
  },

  async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
    return executeReviewEvidenceTool(params, ctx);
  },
});

export default function reviewEvidenceExtension(pi: ExtensionAPI) {
  pi.registerTool(reviewEvidenceTool);
}
