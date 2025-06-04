<script>
document.addEventListener('DOMContentLoaded', async function() {
    const userId = localStorage.getItem('userId');
    const userData = JSON.parse(localStorage.getItem('workTimeUser'));

    if (!userId || !userData) {
        window.location.href = '/login.html';
        return;
    }

    // Page elements
    const shiftsTableBody = document.querySelector('table tbody');
    const addShiftButtonTrigger = Array.from(document.querySelectorAll('button .truncate')).find(el => el.textContent.trim() === 'Aggiungi Turno')?.closest('button');
    const monthYearDisplay = document.querySelector('h2.text-\\[#101418\\].text-\\[22px\\]');

    // Default display month/year (can be updated by calendar controls later)
    let currentDisplayYear = 2024; // Example, ideally get from UI or current date
    let currentDisplayMonth = 10;  // Example, October

    // --- Modal Elements ---
    const addShiftModal = document.getElementById('addShiftModal');
    const addShiftForm = document.getElementById('addShiftForm'); // The form element itself
    const cancelModalButton = document.getElementById('cancelModalButton');
    const submitShiftButton = document.getElementById('submitShiftButton'); // The button in modal footer
    const modalMessageEl = document.getElementById('addShiftModalMessage');
    const shiftDateInput = document.getElementById('shiftDate');
    const shiftStartTimeInput = document.getElementById('shiftStartTime');
    const shiftEndTimeInput = document.getElementById('shiftEndTime');
    const shiftLocationInput = document.getElementById('shiftLocation');


    function showUIMessageGT(message, type = 'info') {
        // For modal messages specifically
        if (addShiftModal && addShiftModal.classList.contains('flex') && modalMessageEl) {
             modalMessageEl.textContent = message;
             modalMessageEl.className = `text-sm ${type === 'error' ? 'text-red-600' : 'text-green-600'}`;
        } else {
            // Fallback to alert for general page messages if modal not active or no dedicated page message area
            alert(message);
        }
        console.log(`GestioneTurni UI Message (${type}): ${message}`);
    }

    function toggleModal(show) {
        if (!addShiftModal || !addShiftForm) return;
        if (show) {
            addShiftModal.classList.remove('hidden');
            addShiftModal.classList.add('flex');
        } else {
            addShiftModal.classList.add('hidden');
            addShiftModal.classList.remove('flex');
            addShiftForm.reset();
            if(modalMessageEl) modalMessageEl.textContent = '';
        }
    }

    async function fetchAndDisplayShifts(year, month) {
        if (!shiftsTableBody) {
            console.error("Shifts table body not found");
            return;
        }
        shiftsTableBody.innerHTML = '';

        try {
            const response = await fetch(`/shifts?user_id=${userId}&year=${year}&month=${month}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            const shifts = await response.json();

            if (shifts.length === 0) {
                shiftsTableBody.innerHTML = '<tr><td colspan="4" class="text-center py-4 text-gray-500">Nessun turno programmato per questo mese.</td></tr>';
                return;
            }

            shifts.forEach(shift => {
                const startTime = new Date(`1970-01-01T${shift.start_time}`).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const endTime = new Date(`1970-01-01T${shift.end_time}`).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const shiftDate = new Date(shift.date);
                const formattedDate = `${shiftDate.getDate()} ${shiftDate.toLocaleString('it-IT', { month: 'short' }).replace('.', '')}`;

                const row = `
                    <tr class="border-t border-t-[#d4dbe2]">
                        <td class="h-[72px] px-4 py-2 text-[#101418] text-sm font-normal leading-normal">${formattedDate}</td>
                        <td class="h-[72px] px-4 py-2 text-[#5c728a] text-sm font-normal leading-normal">${startTime} - ${endTime}</td>
                        <td class="h-[72px] px-4 py-2 text-[#5c728a] text-sm font-normal leading-normal">${shift.location || 'N/A'}</td>
                        <td class="h-[72px] px-4 py-2 text-sm font-normal leading-normal">
                            <button class="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-xl h-8 px-4 bg-[#eaedf1] text-[#101418] text-sm font-medium leading-normal w-full">
                                <span class="truncate">${shift.status || 'Confermato'}</span>
                            </button>
                        </td>
                    </tr>
                `;
                shiftsTableBody.insertAdjacentHTML('beforeend', row);
            });
        } catch (error) {
            console.error('Failed to fetch shifts:', error);
            shiftsTableBody.innerHTML = \`<tr><td colspan="4" class="text-center py-4 text-red-500">Errore nel caricare i turni: ${error.message}</td></tr>\`;
        }
    }

    // Event listener for the main "Aggiungi Turno" button on the page
    if (addShiftButtonTrigger) {
        addShiftButtonTrigger.addEventListener('click', () => {
            // Set current date in modal form
            if (shiftDateInput) {
                 shiftDateInput.valueAsDate = new Date();
            }
            toggleModal(true);
        });
    }

    // Event listener for modal's cancel button
    if (cancelModalButton) {
        cancelModalButton.addEventListener('click', () => toggleModal(false));
    }

    // Event listener for modal's submit button (the one in the footer of the modal)
    if (submitShiftButton) {
        submitShiftButton.addEventListener('click', async () => {
            if (!shiftDateInput || !shiftStartTimeInput || !shiftEndTimeInput || !shiftLocationInput || !modalMessageEl) return;

            const date = shiftDateInput.value;
            const startTime = shiftStartTimeInput.value;
            const endTime = shiftEndTimeInput.value;
            const location = shiftLocationInput.value;

            modalMessageEl.textContent = '';

            if (!date || !startTime || !endTime) {
                showUIMessageGT('Data, Ora Inizio e Ora Fine sono obbligatori.', 'error');
                return;
            }
            if (startTime >= endTime) {
                showUIMessageGT('L\'ora di inizio deve essere precedente all\'ora di fine.', 'error');
                return;
            }

            const shiftData = {
                user_id: parseInt(userId),
                date: date, start_time: startTime, end_time: endTime, location: location
            };

            try {
                const response = await fetch('/shifts', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(shiftData)
                });
                const responseData = await response.json();
                if (response.ok) {
                    showUIMessageGT('Turno aggiunto con successo!', 'success'); // success type
                    toggleModal(false);
                    // Determine which month/year to refresh based on the added shift's date
                    const addedShiftDate = new Date(date);
                    fetchAndDisplayShifts(addedShiftDate.getFullYear(), addedShiftDate.getMonth() + 1);
                } else {
                    showUIMessageGT(responseData.message || 'Errore nell\'aggiungere il turno.', 'error');
                }
            } catch (error) {
                console.error('Error submitting new shift:', error);
                showUIMessageGT('Errore di connessione o API.', 'error');
            }
        });
    }

    // Determine initial month/year to display (e.g. from h2 or current date)
    if (monthYearDisplay && monthYearDisplay.textContent) {
        const parts = monthYearDisplay.textContent.split(" "); // "Ottobre 2024"
        if (parts.length === 2) {
            const monthName = parts[0];
            const yearNum = parseInt(parts[1]);
            const monthMap = {"gennaio":1, "febbraio":2, "marzo":3, "aprile":4, "maggio":5, "giugno":6, "luglio":7, "agosto":8, "settembre":9, "ottobre":10, "novembre":11, "dicembre":12};
            const monthNum = monthMap[monthName.toLowerCase()];
            if(monthNum && !isNaN(yearNum)) {
                currentDisplayYear = yearNum;
                currentDisplayMonth = monthNum;
            } else { // Default to current month if parsing fails
                 const today = new Date(); currentDisplayYear = today.getFullYear(); currentDisplayMonth = today.getMonth() + 1;
            }
        }
    } else { // Default to current month if no display
        const today = new Date(); currentDisplayYear = today.getFullYear(); currentDisplayMonth = today.getMonth() + 1;
    }


    fetchAndDisplayShifts(currentDisplayYear, currentDisplayMonth);

    // TODO: Implement calendar population and month navigation for the two calendars.
});
</script>
