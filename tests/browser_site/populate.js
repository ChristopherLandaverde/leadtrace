// Synthetic landing-page script: copies URL params into hidden inputs.
// Walkthrough fixture / no client data.
(function () {
  var params = new URLSearchParams(window.location.search);
  var skip = (document.body.dataset.skip || "").split(",");
  ["utm_source", "utm_medium", "utm_campaign", "gclid", "fbclid"].forEach(function (name) {
    var input = document.querySelector('input[type=hidden][name="' + name + '"]');
    if (input && skip.indexOf(name) === -1) input.value = params.get(name) || "";
  });
  var conv = document.querySelector('input[name="original_conversion_id"]');
  if (conv) conv.value = "conv_page_" + Math.random().toString(16).slice(2);
})();
