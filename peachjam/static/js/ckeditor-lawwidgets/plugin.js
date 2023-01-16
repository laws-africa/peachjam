(function () {
  CKEDITOR.plugins.add('lawwidgets', {
    icons: 'scales',
    init: function (editor) {
      // Define an editor command that opens our dialog window.
      editor.addCommand('laakn', new CKEDITOR.dialogCommand('laaknDialog', {
        // Allow the la-akoma-ntoso tag
        allowedContent: 'la-akoma-ntoso[fetch,frbr-expression-uri,partner]',
        // Require the abbr tag to be allowed for the feature to work.
        requiredContent: 'la-akoma-ntoso'
      }));

      // create a toolbar button for the command
      editor.ui.addButton('LaAkn', {
        label: 'Insert Law Widget',
        command: 'laakn',
        toolbar: 'insert',
        icon: 'scales'
      });

      if (editor.contextMenu) {
        editor.addMenuGroup('lawWidgetsGroup');
        editor.addMenuItem('laaknItem', {
          label: 'Edit Law Widget',
          icon: this.path + 'icons/abbr.png',
          command: 'laakn',
          group: 'lawWidgetsGroup'
        });

        editor.contextMenu.addListener(function(element) {
          if (element.getAscendant('la-akoma-ntoso', true)) {
            return { abbrItem: CKEDITOR.TRISTATE_OFF };
          }
        });
      }

      // register dialog
      CKEDITOR.dialog.add('laaknDialog', this.path + 'dialog.js');
    },
    onLoad: function () {
      CKEDITOR.addCss(
        'la-akoma-ntoso::before { content: "Law Widget: " attr(frbr-expression-uri) " "; } ' +
        'la-akoma-ntoso { border: 1px solid purple; }'
      );
    }
  });
})();
