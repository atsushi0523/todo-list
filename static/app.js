// 完了チェックを押したらすぐに送信する
document.querySelectorAll(".js-auto-submit").forEach((checkbox) => {
  checkbox.addEventListener("change", () => checkbox.form.submit());
});

// 削除の前に確認ダイアログを出す（メッセージは data-confirm 属性から読む）
document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});
