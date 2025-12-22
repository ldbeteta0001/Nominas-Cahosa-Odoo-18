/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.QuitRequestForm = publicWidget.Widget.extend({
    selector: '.advance_request_form_js_class',
    events: {
        'click #add_advance': '_onSubmitForm',
        'change input': '_check_and_save_value',
        'change textarea': '_check_and_save_value',
        'change select': '_check_select_and_save_value',
        'click .delete-button': '_remove_from_list',
    },

    /**
     * @constructor
     */
    init: function (parent, options) {
        console.log("entró aqui")
        this.options = {};
        this._super.apply(this, arguments);
//      data form values
//       Inicializar 'quit_date' con la fecha actual
        var currentDate = new Date();
        var day = ("0" + currentDate.getDate()).slice(-2);
        var month = ("0" + (currentDate.getMonth() + 1)).slice(-2);
        var year = currentDate.getFullYear();

        this.loan_date = year + "-" + month + "-" + day;
        this.error_quit_request = false;
        this.error_general = false;
    },
    _onSubmitForm: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        console.log('submit form')
        this._validate_fields()
        // Coger el valor al campo input en la vista
        var inputDate = document.getElementById("date");
        var inputEmployeeId = document.getElementById("employee_id");
        var inputAdvance = document.getElementById("advance");
        var inputReason = document.getElementById("reason");

        let advance_request = {
         'date': inputDate ? inputDate.value : '',
         'employee_id': inputEmployeeId ? inputEmployeeId.value : '',
         'advance': inputAdvance ? inputAdvance.value : '',
         'reason': inputReason ? inputReason.value : '',
        }
        
        console.log("Datos a enviar:", advance_request);

        if (!this.error_general){
            rpc("/safe_hr_advance", {
                'advance_request': advance_request,
            }).then(function(result){
                console.log("Respuesta del servidor:", result)
                if (result && result.success) {
                    window.location.href = '/advance/answer_form';
                } else {
                    alert("Error al guardar: " + (result.error || "Error desconocido"));
                }
            }).catch(function(error){
                console.error("Error al guardar:", error);
                alert("Error al guardar el adelanto. Por favor, intente nuevamente.");
            })
        } else {
            console.log("Hay errores de validación, no se envía el formulario");
        }

    },
    _check_and_save_value: function(ev){
        ev.preventDefault();
        ev.stopPropagation();
        this[ev.target.name] = ev.target.value;
    },
    _validate_fields: function(){
        var inputDate = document.getElementById("date");
        var inputAdvance = document.getElementById("advance");
        var inputReason = document.getElementById("reason");
        var inputEmployeeId = document.getElementById("employee_id");
        
        this.error_general = false;

        if (!inputDate || !inputDate.value || inputDate.value == ''){
            var input_date = document.getElementById('input_date');
            if (input_date) {
                input_date.classList.remove("d-none");
                input_date.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            }
            this.error_general = true;
        }else{
            var input_date = document.getElementById('input_date');
            if (input_date) {
                input_date.classList.add("d-none");
            }
        }
        
        if (!inputAdvance || !inputAdvance.value || inputAdvance.value == '' || parseFloat(inputAdvance.value) <= 0){
            var input_advance = document.getElementById('input_advance');
            if (input_advance) {
                input_advance.classList.remove("d-none");
                input_advance.innerHTML = "<small class='text-danger'>Debe llenar este campo con un valor mayor a 0</small>";
            }
            this.error_general = true;
        }else{
            var input_advance = document.getElementById('input_advance');
            if (input_advance) {
                input_advance.classList.add("d-none");
            }
        }
        
        if (!inputReason || !inputReason.value || inputReason.value.trim() == ''){
            var input_reason = document.getElementById('input_reason');
            if (input_reason) {
                input_reason.classList.remove("d-none");
                input_reason.innerHTML = "<small class='text-danger'>Debe llenar este campo</small>";
            }
            this.error_general = true;
        }else{
            var input_reason = document.getElementById('input_reason');
            if (input_reason) {
                input_reason.classList.add("d-none");
            }
        }
    },
    validate_request: function(){
        console.log("validate")
        let employee_id = this.employee_id;
        let date = this.date;

        this.error_load_request = false;
        if (employee_id == ''){
            var input_employee_id = document.getElementById('employee_id');
            input_employee_id.classList.remove("d-none");
            input_employee_id.innerHTML = "<small class='text-danger'>Debe definir el empleado</small>";
            this.error_load_request = true;
        }else{
            var input_employee_id = document.getElementById('employee_id');
            input_employee_id.classList.add("d-none");
        }
    },

    });
