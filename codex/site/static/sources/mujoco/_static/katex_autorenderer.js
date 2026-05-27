katex_options = {
macros: {"\\d":             "\\operatorname{#1}",
"\\ar":            "a_{\\rm ref}",
"\\au":            "a_0",
"\\ac":            "a_1",
"\\ari":           "a_{{\\rm ref},i}",
"\\aui":           "a_{0,i}",
"\\aci":           "a_{1,i}",
"\\nv":            "n_{\\scriptscriptstyle V}",
"\\nc":            "n_{\\scriptscriptstyle C}",
"\\nq":            "n_{\\scriptscriptstyle Q}",},
delimiters: [
        { left: "\\(", right: "\\)", display: false },
        { left: "\\[", right: "\\]", display: true }
        ]
}
document.addEventListener("DOMContentLoaded", function() {
  renderMathInElement(document.body, katex_options);
});
