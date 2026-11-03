export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  /** 展示时间：台上显示为 22:41，不参与协议。 */
  at: number;
  /** 被打断的 assistant 回复（3.4 turn_complete status=CANCELLED）。 */
  interrupted?: boolean;
  /** 协议/网络错误：渲染成提示条，不伪装成她的一句话。 */
  kind?: "error";
  /** 错误码，用于「一键切换链路」。 */
  code?: string;
}
