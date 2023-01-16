CKEDITOR.dialog.add('laaknDialog', function (editor) {
  return {

    // Basic properties of the dialog window: title, minimum size.
    title: 'Law Widget Properties',
    minWidth: 400,
    minHeight: 200,

    // Dialog window content definition.
    contents: [
      {
        // Definition of the Basic Settings dialog tab (page).
        id: 'tab-basic',
        label: 'Basic Settings',

        // The tab content.
        elements: [
          {
            // Text input field for the abbreviation text.
            type: 'text',
            id: 'frbr-expression-uri',
            label: 'FRBR Expression URI',

            // Validation checking whether the field is not empty.
            validate: CKEDITOR.dialog.validate.notEmpty('FRBR Expression URI field cannot be empty.'),

            // Called by the main setupContent method call on dialog initialization.
            setup: function (element) {
              this.setValue(element.getAttribute('frbr-expression-uri'));
            },

            // Called by the main commitContent method call on dialog confirmation.
            commit: function (element) {
              element.setText('Content loading...');
              element.setAttribute('frbr-expression-uri', this.getValue());
              element.setAttribute('fetch', 'fetch');
              const partner = window.location.hostname === 'localhost' ? 'laws.africa' : window.location.hostname;
              element.setAttribute('partner', partner);
            }
          }
        ]
      }
    ],

    // Invoked when the dialog is loaded.
    onShow: function () {
      var selection = editor.getSelection();
      var element = selection.getStartElement();

      // Get the <abbr> element closest to the selection, if it exists.
      if (element) {
        element = element.getAscendant('la-akoma-ntoso', true);
      }

      // Create a new <abbr> element if it does not exist.
      if (!element || element.getName() !== 'la-akoma-ntoso') {
        element = editor.document.createElement('la-akoma-ntoso');

        // Flag the insertion mode for later use.
        this.insertMode = true;
      } else {
        this.insertMode = false;
      }

      // Store the reference to the <abbr> element in an internal property, for later use.
      this.element = element;

      // Invoke the setup methods of all dialog window elements, so they can load the element attributes.
      if (!this.insertMode)
        this.setupContent(this.element);
    },

    // This method is invoked once a user clicks the OK button, confirming the dialog.
    onOk: function () {
      // The context of this function is the dialog object itself.
      // https://ckeditor.com/docs/ckeditor4/latest/api/CKEDITOR_dialog.html
      var el = this.element;

      this.commitContent(el);

      // Finally, if in insert mode, insert the element into the editor at the caret position.
      if (this.insertMode)
        editor.insertElement(el);
    }
  };
});
