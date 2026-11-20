import React from "react";

import "./AssistantMessage.css";

function AssistantMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`assistant-message-row ${
        isUser ? "assistant-message-user" : "assistant-message-ai"
      }`}
    >
      {!isUser && (
        <div className="assistant-message-avatar">
          A
        </div>
      )}

      <div className="assistant-message-content">
        <span className="assistant-message-role">
          {isUser ? "YOU" : "FINANCE AI"}
        </span>

        <div className="assistant-message-bubble">
          {message.content}
        </div>
      </div>

      {isUser && (
        <div className="assistant-message-avatar assistant-user-avatar">
          B
        </div>
      )}
    </div>
  );
}

export default AssistantMessage;
