// 端末で「視差効果を減らす」が選ばれているか
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// 完了チェックを押したら送信する。
// チェックの色は押した瞬間に変わり、行が静かに消えていく動きを見せてから送信する（動きを減らす設定ならすぐ送信）
document.querySelectorAll(".js-auto-submit").forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    const row = checkbox.closest(".todo-item");
    if (reduceMotion || !row) {
      checkbox.form.submit();
      return;
    }
    row.classList.add("is-leaving");
    checkbox.disabled = true; // 二度押しで二重に送信しないように
    window.setTimeout(() => {
      checkbox.disabled = false; // disabled のままだと送信されないので戻す（値は送らない作りなので影響しない）
      checkbox.form.submit();
    }, 320);
  });
});

// ブラウザの「戻る」で消えかけの状態のページが出てきたときは、元に戻す
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  document.querySelectorAll(".todo-item.is-leaving").forEach((row) => {
    row.classList.remove("is-leaving");
    const checkbox = row.querySelector(".js-auto-submit");
    if (checkbox) checkbox.checked = !checkbox.checked;
  });
});

// 削除の前に確認ダイアログを出す（メッセージは data-confirm 属性から読む）
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

// 上のバー：一番上にいるときは線を出さず、内容がバーの下にもぐったときだけ境目を出す
const appBar = document.querySelector(".app-bar");
if (appBar) {
  const update = () => appBar.classList.toggle("is-scrolled", window.scrollY > 4);
  update();
  window.addEventListener("scroll", update, { passive: true });
}

// 操作後のメッセージ：「完了しました」などの知らせは、数秒たったら自然に消す（警告は残す）
document.querySelectorAll(".toast-success").forEach((toast) => {
  window.setTimeout(() => {
    if (reduceMotion) {
      toast.remove();
      return;
    }
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
    toast.classList.add("is-hiding");
  }, 3500);
});
