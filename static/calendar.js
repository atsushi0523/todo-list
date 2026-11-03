// カレンダーページ：FullCalendar で月表示する。予定のデータはページに埋め込んだ JSON から読む
document.addEventListener("DOMContentLoaded", () => {
  const element = document.getElementById("calendar");
  const events = JSON.parse(document.getElementById("calendar-events").textContent);
  const narrow = window.matchMedia("(max-width: 575.98px)").matches;

  const calendar = new FullCalendar.Calendar(element, {
    locale: "ja",
    // スマートフォンでは月表示だと文字が詰まるので、最初はリスト表示にする
    initialView: narrow ? "listMonth" : "dayGridMonth",
    headerToolbar: { left: "prev,next today", center: "title", right: "dayGridMonth,listMonth" },
    buttonText: { listMonth: "リスト" },
    height: "auto",
    dayMaxEvents: 3,
    eventDisplay: "block",
    displayEventEnd: false,
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    noEventsContent: "この月のやることはありません",
    events: events,
  });
  calendar.render();
});
