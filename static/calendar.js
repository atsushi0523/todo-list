// カレンダーページ：FullCalendar で表示する。予定のデータはページに埋め込んだ JSON から読む
//
// スマートフォンの月表示では、予定を色の点で出し、日付を押すと下にその日のやることを一覧で出す。
// 最後に選んだ表示（月・リスト）は、この端末のブラウザに覚えておく。
document.addEventListener("DOMContentLoaded", () => {
  const element = document.getElementById("calendar");
  const events = JSON.parse(document.getElementById("calendar-events").textContent);
  const compact = window.matchMedia("(max-width: 575.98px)").matches;

  const panel = document.getElementById("day-panel");
  const panelTitle = document.getElementById("day-panel-title");
  const panelList = document.getElementById("day-panel-list");
  const panelAdd = document.getElementById("day-panel-add");

  const VIEW_KEY = "todo.calendarView";
  const VIEWS = ["dayGridMonth", "listMonth"];
  const WEEKDAYS = "日月火水木金土";

  // 保存した表示を読む。プライベートブラウズなどで使えなくても動くようにする
  function savedView() {
    try {
      const view = window.localStorage.getItem(VIEW_KEY);
      return VIEWS.includes(view) ? view : null;
    } catch (e) {
      return null;
    }
  }

  function saveView(view) {
    try {
      window.localStorage.setItem(VIEW_KEY, view);
    } catch (e) {
      // 保存できなくても困らない
    }
  }

  function ymd(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  let selected = ymd(new Date());

  // その日を期日に入れた登録ページのURL。保存やキャンセルのあとはカレンダーに戻る
  function newTodoUrl(dateStr) {
    const params = new URLSearchParams({ due_date: dateStr, next: "calendar" });
    return `${element.dataset.newUrl}?${params}`;
  }

  // 選んだ日の数字に印をつける（月を移動すると描き直されるので、そのたびにつけ直す）
  function markSelected() {
    element.querySelectorAll(".fc-daygrid-day.is-selected").forEach((cell) => cell.classList.remove("is-selected"));
    const cell = element.querySelector(`.fc-daygrid-day[data-date="${selected}"]`);
    if (cell) cell.classList.add("is-selected");
  }

  // 選んだ日のやることを、下の一覧に出す。文字は textContent で入れるので、タイトルに記号があっても安全
  function renderDay(dateStr) {
    selected = dateStr;
    markSelected();

    const [y, m, d] = dateStr.split("-").map(Number);
    const weekday = WEEKDAYS[new Date(y, m - 1, d).getDay()];
    panelTitle.textContent = `${m}月${d}日（${weekday}）のやること`;
    panelAdd.href = newTodoUrl(dateStr);

    const items = events
      .filter((event) => event.start.slice(0, 10) === dateStr)
      .sort((a, b) => (a.allDay === b.allDay ? a.start.localeCompare(b.start) : a.allDay ? 1 : -1));

    panelList.replaceChildren();
    if (items.length === 0) {
      const li = document.createElement("li");
      li.className = "ios-row day-empty";
      li.textContent = "やることはありません";
      panelList.append(li);
      return;
    }
    for (const event of items) {
      const li = document.createElement("li");
      const link = document.createElement("a");
      link.className = "ios-row";
      link.href = event.url;

      const dot = document.createElement("span");
      dot.className = "day-dot";
      dot.style.backgroundColor = event.color;

      const title = document.createElement("span");
      title.className = "ios-row-body todo-title";
      title.textContent = event.title;
      if (event.classNames.includes("todo-event-done")) title.style.textDecoration = "line-through";

      const time = document.createElement("span");
      time.className = "day-time";
      time.textContent = event.allDay ? "終日" : event.start.slice(11, 16);

      const chevron = document.createElement("span");
      chevron.className = "day-chevron";
      chevron.setAttribute("aria-hidden", "true");
      chevron.textContent = "›";

      link.append(dot, title, time, chevron);
      li.append(link);
      panelList.append(li);
    }
  }

  const calendar = new FullCalendar.Calendar(element, {
    locale: "ja",
    initialView: savedView() || "dayGridMonth",
    headerToolbar: { left: "prev,next today", center: "title", right: "dayGridMonth,listMonth" },
    buttonText: { listMonth: "リスト" },
    height: "auto",
    fixedWeekCount: false,
    dayMaxEvents: compact ? false : 3,
    eventDisplay: "block",
    displayEventEnd: false,
    eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
    noEventsContent: "この月のやることはありません",
    // スマートフォンの月表示では「1日」ではなく「1」とだけ出す
    dayCellContent: compact ? (arg) => String(arg.date.getDate()) : undefined,
    events: events,

    // 表示や月が変わったとき
    datesSet: (info) => {
      saveView(info.view.type);
      const useDots = compact && info.view.type === "dayGridMonth";
      element.classList.toggle("calendar-compact", useDots);
      panel.hidden = !useDots;
      if (!useDots) return;
      // 選んでいた日がこの月になければ、今日（今月なら）か月の初めを選ぶ
      const start = ymd(info.view.currentStart);
      const end = ymd(info.view.currentEnd);
      if (selected < start || selected >= end) {
        const today = ymd(new Date());
        selected = today >= start && today < end ? today : start;
      }
      requestAnimationFrame(() => renderDay(selected));
    },

    // 日付を押したとき：スマートフォンの月表示ではその日を選び（下の一覧から追加できる）、
    // それ以外では、その日を期日にした登録ページを開く
    dateClick: (info) => {
      if (element.classList.contains("calendar-compact")) {
        renderDay(info.dateStr);
      } else if (info.view.type === "dayGridMonth") {
        window.location.href = newTodoUrl(info.dateStr);
      }
    },

    // 予定を押したとき：スマートフォンの月表示では点が小さいので、その日を選ぶだけにする
    eventClick: (info) => {
      if (element.classList.contains("calendar-compact")) {
        info.jsEvent.preventDefault();
        renderDay(ymd(info.event.start));
      }
    },
  });
  calendar.render();
});
