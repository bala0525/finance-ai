import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getNotifications, markNotificationRead, markAllNotificationsRead } from "../../services/notificationService";
import "./NotificationBell.css";

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const refresh = async () => {
    try { const data = await getNotifications(); setItems(data.items || []); setUnread(data.unreadCount || 0); setError(""); }
    catch (e) { setError(e.message); }
  };
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 60000); return () => window.clearInterval(timer); }, []);
  const openItem = async (item) => {
    if (!item.read) { try { await markNotificationRead(item.id); } catch (e) { setError(e.message); } }
    await refresh(); setOpen(false); if (item.link) navigate(item.link);
  };
  const readAll = async () => { try { await markAllNotificationsRead(); await refresh(); } catch (e) { setError(e.message); } };
  return <div className="notification-root">
    <button type="button" className="notification-trigger" onClick={() => { setOpen(v => !v); if (!open) refresh(); }} aria-label={`Notifications, ${unread} unread`}>
      <span aria-hidden="true">♢</span>{unread > 0 && <b>{unread > 99 ? "99+" : unread}</b>}
    </button>
    {open && <div className="notification-popover">
      <div className="notification-heading"><strong>Notifications</strong><button type="button" onClick={readAll} disabled={!unread}>Mark all read</button></div>
      {error && <p className="notification-error">{error}</p>}
      {items.length === 0 ? <p className="notification-empty">You're all caught up.</p> : items.map(item => <button key={item.id} type="button" className={`notification-item ${item.read ? "" : "unread"}`} onClick={() => openItem(item)}>
        <strong>{item.title}</strong><span>{item.message}</span><small>{item.createdAt ? new Date(item.createdAt).toLocaleString() : ""}</small>
      </button>)}
    </div>}
  </div>;
}
