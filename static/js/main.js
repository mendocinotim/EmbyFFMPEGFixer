document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const embyPathInput = document.getElementById('embyPath');
    const browseButton = document.getElementById('browseEmby');
    const usePathButton = document.getElementById('useThisPath');
    const selectedPathDisplay = document.getElementById('selected-path');
    const checkCompatibilityButton = document.getElementById('check-compatibility');
    const stopProcessButton = document.getElementById('stop-process');
    const compatibilityResults = document.getElementById('compatibility-results');
    const systemArchitectureElement = document.getElementById('system-architecture');
    const ffmpegArchitectureElement = document.getElementById('ffmpeg-architecture');
    const compatibilityStatusElement = document.getElementById('compatibility-status');
    const fixSection = document.getElementById('fix-section');
    const fixButton = document.getElementById('fix-compatibility');
    const fixStatusElement = document.getElementById('fix-status');
    const restoreSection = document.getElementById('restore-section');
    const checkBackupButton = document.getElementById('check-backup-button');
    const backupStatusElement = document.getElementById('backup-status');
    const restoreButton = document.getElementById('restore-button');
    const restoreStatusElement = document.getElementById('restore-status');
    const downloadLogButton = document.getElementById('download-log-button');
    const viewLogButton = document.getElementById('view-log-button');
    const logContainer = document.getElementById('log-container');
    const logEntries = document.getElementById('log-entries');

    // State
    let selectedEmbyPath = '';
    let isCompatible = false;
    let currentStep = null;
    let isProcessing = false;

    let serverList;

    // Event Listeners
    if (stopProcessButton) {
        stopProcessButton.addEventListener('click', function() {
            if (isProcessing) {
                stopProcess();
            }
        });
        
        // Initialize stop button state
        stopProcessButton.disabled = true;
        stopProcessButton.classList.add('disabled');
        stopProcessButton.setAttribute('title', 'No process running');
        stopProcessButton.style.cursor = 'not-allowed';
        stopProcessButton.style.opacity = '0.65';
    }
    
    // Enable buttons that should be active on load
    browseButton.disabled = false;
    usePathButton.disabled = false;

    // Initialize the application
    initializeApp();

    // Progress tracking
    const progressSteps = {
        'check-compatibility': { progress: 0, status: 'pending' },
        'fix-compatibility': { progress: 0, status: 'pending' },
        'restore': { progress: 0, status: 'pending' }
    };

    function updateProgress(step, progress, status = null) {
        if (progressSteps[step]) {
            progressSteps[step].progress = progress;
            if (status) {
                progressSteps[step].status = status;
            }

            const progressBar = document.querySelector(`.progress-item[data-step="${step}"] .progress-bar`);
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
                progressBar.classList.remove('complete', 'error', 'stalled');
                if (status) {
                    progressBar.classList.add(status);
                }
            }
        }
    }

    function resetProgress() {
        Object.keys(progressSteps).forEach(step => {
            progressSteps[step].progress = 0;
            progressSteps[step].status = 'pending';
            updateProgress(step, 0);
        });
    }

    function setProcessing(processing) {
        console.log('Setting processing state:', processing); // Debug log
        isProcessing = processing;
        
        // Update stop button state
        if (stopProcessButton) {
            stopProcessButton.disabled = !processing;
            stopProcessButton.classList.toggle('disabled', !processing);
            stopProcessButton.style.cursor = processing ? 'pointer' : 'not-allowed';
            stopProcessButton.style.opacity = processing ? '1' : '0.65';
            stopProcessButton.title = processing ? 'Stop current process' : 'No process running';
            
            if (processing) {
                stopProcessButton.classList.add('active');
                console.log('Stop button activated'); // Debug log
            } else {
                stopProcessButton.classList.remove('active');
                console.log('Stop button deactivated'); // Debug log
            }
        }
        
        // Update other button states
        if (checkCompatibilityButton) checkCompatibilityButton.disabled = processing;
        if (fixButton) fixButton.disabled = processing;
        if (restoreButton) restoreButton.disabled = processing;
        if (checkBackupButton) checkBackupButton.disabled = processing;
        
        // Update progress bars if stopping
        if (!processing) {
            resetProgress();
        }
    }

    function stopProcess() {
        if (!isProcessing) return;

        const mainEntryId = addLogEntry('Stopping process...', 'active');
        setProcessing(true); // Keep processing state while stopping
        
        // Disable all buttons while stopping
        if (checkCompatibilityButton) checkCompatibilityButton.disabled = true;
        if (fixButton) fixButton.disabled = true;
        if (restoreButton) restoreButton.disabled = true;
        if (checkBackupButton) checkBackupButton.disabled = true;
        if (stopProcessButton) stopProcessButton.disabled = true;
        
        fetch('/api/stop-process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                path: embyPathInput.value.trim()
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                addLogEntry('Process stopped successfully', 'complete', true, mainEntryId);
                addLogEntry('Restoring to initial state...', 'active', true, mainEntryId);
                
                // Reset all progress bars
                resetProgress();
                
                // Update current step's progress to stopped state
                if (currentStep) {
                    updateProgress(currentStep, 100, 'error');
                }
                
                // Clear results and reset UI
                if (compatibilityResults) compatibilityResults.classList.add('hidden');
                if (fixSection) fixSection.classList.add('hidden');
                if (restoreSection) restoreSection.classList.add('hidden');
                
                addLogEntry('Initial state restored, redirecting to start page...', 'complete', true, mainEntryId);
                
                // Handle redirect after a short delay
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1000);
            } else {
                throw new Error(data.message || 'Failed to stop process');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            addLogEntry(`Failed to stop process: ${error.message}`, 'error', true, mainEntryId);
            // Re-enable buttons on error
            setProcessing(false);
        });
    }

    function initializeApp() {
        const currentDate = new Date().toISOString().substring(0, 10);
        const currentTime = new Date().toTimeString().substring(0, 8);
        addLogEntry(`${currentDate} ${currentTime} Initialization`, 'complete');
        
        // Check current processing state from server
        fetch('/api/process-state')
            .then(response => response.json())
            .then(data => {
                setProcessing(data.is_processing);
                if (data.is_processing) {
                    addLogEntry('Process is currently running', 'active');
                }
            })
            .catch(error => {
                console.error('Error getting process state:', error);
                setProcessing(false);
            });
        
        // If there's a pre-populated path, trigger the path selection
        if (embyPathInput && embyPathInput.value) {
            selectedEmbyPath = embyPathInput.value;
            updateSelectedPath(embyPathInput.value);
            addLogEntry(`Selected Emby Server path: ${embyPathInput.value}`, 'complete');
        } else {
            // Try to get default path from server
            fetch('/api/get-default-path')
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.path) {
                        selectedEmbyPath = data.path;
                        embyPathInput.value = data.path;
                        updateSelectedPath(data.path);
                        addLogEntry(`Found default Emby Server path: ${data.path}`, 'complete');
                    }
                })
                .catch(error => {
                    console.error('Error getting default path:', error);
                });
        }

        serverList = document.createElement('select');
        serverList.id = 'server-list';
        serverList.className = 'server-list';
        serverList.style.display = 'none';
        embyPathInput.parentNode.insertBefore(serverList, embyPathInput.nextSibling);
    }

    // Functions
    function updateSelectedPath(path) {
        selectedEmbyPath = path;
        selectedPathDisplay.textContent = path;
        checkCompatibilityButton.disabled = false;
        checkBackupButton.disabled = false;
        
        // Reset compatibility results
        compatibilityResults.classList.add('hidden');
        fixSection.classList.add('hidden');
        fixStatusElement.classList.add('hidden');
        backupStatusElement.classList.add('hidden');
        restoreButton.classList.add('hidden');
        restoreStatusElement.classList.add('hidden');
    }

    // Function to select Emby path
    function selectEmbyPath(path) {
        return new Promise((resolve, reject) => {
            fetch('/api/select-emby', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    path: path.replace(/\\/g, '/') // Normalize path separators
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update selected path display
                    document.getElementById('selected-path').textContent = path;
                    selectedEmbyPath = path;
                    
                    // Enable buttons
                    document.getElementById('check-compatibility').disabled = false;
                    if (checkBackupButton) checkBackupButton.disabled = false;
                    
                    // Automatically trigger compatibility check
                    checkCompatibility();
                    
                    resolve(data);
                } else {
                    reject(new Error(data.message));
                }
            })
            .catch(error => reject(error));
        });
    }

    function checkCompatibility() {
        const path = embyPathInput.value.trim();
        if (!path) {
            alert('Please enter or select an Emby Server path first');
            return;
        }

        setProcessing(true);
        currentStep = 'check-compatibility';
        updateProgress('check-compatibility', 10);
        addLogEntry('Checking FFMPEG compatibility...', 'info');

        // Show the results table immediately but with loading state
        document.getElementById('system-architecture').textContent = 'Checking...';
        document.getElementById('ffmpeg-architecture').textContent = 'Checking...';
        document.getElementById('compatibility-status').textContent = 'Checking...';
        document.getElementById('compatibility-results').classList.remove('hidden');

        fetch('/api/check-compatibility', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: path })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            updateProgress('check-compatibility', 50);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Update architecture information
                document.getElementById('system-architecture').textContent = data.system_architecture || 'Unknown';
                document.getElementById('ffmpeg-architecture').textContent = data.ffmpeg_architecture || 'Unknown';
                document.getElementById('compatibility-status').textContent = data.is_compatible ? 'Compatible ✅' : 'Incompatible ❌';
                
                // Update progress and log
                updateProgress('check-compatibility', 100, 'complete');
                addLogEntry(`System Architecture: ${data.system_architecture}`, 'info', true);
                addLogEntry(`FFMPEG Architecture: ${data.ffmpeg_architecture}`, 'info', true);
                addLogEntry(`Compatibility Status: ${data.is_compatible ? 'Compatible' : 'Incompatible'}`, data.is_compatible ? 'success' : 'error', true);
                
                // Show fix section if incompatible
                if (!data.is_compatible) {
                    document.getElementById('fix-section').classList.remove('hidden');
                    fixButton.disabled = false;
                }
            } else {
                throw new Error(data.message || 'Failed to check compatibility');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            // Update status elements to show error
            document.getElementById('system-architecture').textContent = 'Error';
            document.getElementById('ffmpeg-architecture').textContent = 'Error';
            document.getElementById('compatibility-status').textContent = 'Check Failed ❌';
            updateProgress('check-compatibility', 100, 'error');
            addLogEntry(`Error checking compatibility: ${error.message}`, 'error');
        })
        .finally(() => {
            setProcessing(false);
        });
    }

    function fixFFMPEG() {
        if (!selectedEmbyPath) {
            alert('Please select Emby Server path first');
            return;
        }

        if (isCompatible) {
            alert('FFMPEG is already compatible with your system');
            return;
        }

        setProcessing(true);  // Set processing state at the start
        addLogEntry('Fixing FFMPEG Compatibility...', 'active');
        
        fetch('/api/fix-ffmpeg', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: selectedEmbyPath })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                fixStatusElement.textContent = '✅ ' + data.message;
                fixStatusElement.className = 'status-message success';
                addLogEntry('Fixing FFMPEG Compatibility...', 'complete');
                addLogEntry(data.message);
                
                // After fixing, re-check compatibility
                setTimeout(checkCompatibility, 1000);
            } else {
                fixStatusElement.textContent = '❌ ' + data.message;
                fixStatusElement.className = 'status-message error';
                addLogEntry('Fixing FFMPEG Compatibility...', 'error');
                addLogEntry(data.message, 'error');
                setProcessing(false);  // Set processing to false on error
            }
            
            fixStatusElement.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error:', error);
            fixStatusElement.textContent = '❌ An error occurred while fixing FFMPEG compatibility';
            fixStatusElement.className = 'status-message error';
            fixStatusElement.classList.remove('hidden');
            addLogEntry(`Error: ${error.message}`, 'error');
            setProcessing(false);  // Set processing to false on error
        });
    }

    function checkBackup() {
        if (!selectedEmbyPath) {
            alert('Please select Emby Server path first');
            return;
        }

        addLogEntry('Checking for FFMPEG backup...', 'active');
        
        fetch('/api/check-backup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: selectedEmbyPath })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.has_backup) {
                    backupStatusElement.textContent = '✅ Original FFMPEG backup found';
                    backupStatusElement.className = 'status-message success';
                    restoreButton.classList.remove('hidden');
                    addLogEntry('Original FFMPEG backup found');
                } else {
                    backupStatusElement.textContent = 'ℹ️ No original FFMPEG backup found';
                    backupStatusElement.className = 'status-message info';
                    restoreButton.classList.add('hidden');
                    addLogEntry('No original FFMPEG backup found');
                }
                
                addLogEntry('Checking for FFMPEG backup...', 'complete');
            } else {
                backupStatusElement.textContent = '❌ ' + data.message;
                backupStatusElement.className = 'status-message error';
                restoreButton.classList.add('hidden');
                addLogEntry('Checking for FFMPEG backup...', 'error');
                addLogEntry(data.message, 'error');
            }
            
            backupStatusElement.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error:', error);
            backupStatusElement.textContent = '❌ An error occurred while checking for backup';
            backupStatusElement.className = 'status-message error';
            backupStatusElement.classList.remove('hidden');
            restoreButton.classList.add('hidden');
            addLogEntry(`Error: ${error.message}`, 'error');
        });
    }

    function restoreFFMPEG() {
        if (!selectedEmbyPath) {
            alert('Please select Emby Server path first');
            return;
        }

        if (!confirm('Are you sure you want to restore the original FFMPEG binaries? This will undo any fixes applied by this tool.')) {
            return;
        }

        addLogEntry('Restoring original FFMPEG binaries...', 'active');
        
        fetch('/api/restore-ffmpeg', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: selectedEmbyPath })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                restoreStatusElement.textContent = '✅ ' + data.message;
                restoreStatusElement.className = 'status-message success';
                addLogEntry('Restoring original FFMPEG binaries...', 'complete');
                addLogEntry(data.message);
                
                // After restoring, re-check compatibility
                setTimeout(checkCompatibility, 1000);
            } else {
                restoreStatusElement.textContent = '❌ ' + data.message;
                restoreStatusElement.className = 'status-message error';
                addLogEntry('Restoring original FFMPEG binaries...', 'error');
                addLogEntry(data.message, 'error');
            }
            
            restoreStatusElement.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error:', error);
            restoreStatusElement.textContent = '❌ An error occurred while restoring FFMPEG binaries';
            restoreStatusElement.className = 'status-message error';
            restoreStatusElement.classList.remove('hidden');
            addLogEntry(`Error: ${error.message}`, 'error');
        });
    }

    function downloadLog() {
        window.location.href = '/api/download-log';
    }

    function viewFullLog() {
        addLogEntry('Fetching full log...', 'active');
        
        fetch('/api/get-logs', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                console.error('Response not OK:', response.status, response.statusText);
                if (response.status === 404) {
                    throw new Error('Log file not found');
                } else if (response.status === 500) {
                    throw new Error('Server error while reading logs');
                } else {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
            }
            return response.json().catch(error => {
                console.error('JSON parse error:', error);
                throw new Error('Failed to parse server response');
            });
        })
        .then(data => {
            if (!data) {
                throw new Error('No data received from server');
            }
            
            if (data.success) {
                if (!data.logs) {
                    throw new Error('Log data is empty');
                }
                
                // Create modal to display full log
                const modal = document.createElement('div');
                modal.className = 'modal';
                
                const modalContent = document.createElement('div');
                modalContent.className = 'modal-content';
                
                const closeButton = document.createElement('span');
                closeButton.className = 'close-button';
                closeButton.textContent = '×';
                closeButton.onclick = () => {
                    document.body.removeChild(modal);
                };
                
                const heading = document.createElement('h2');
                heading.textContent = 'Full Log';
                
                const logText = document.createElement('pre');
                logText.className = 'full-log';
                
                try {
                    // Split logs into lines and reverse them
                    const logLines = data.logs.split('\n').reverse();
                    logText.textContent = logLines.join('\n');
                } catch (error) {
                    console.error('Error processing log data:', error);
                    throw new Error('Error processing log data');
                }
                
                modalContent.appendChild(closeButton);
                modalContent.appendChild(heading);
                modalContent.appendChild(logText);
                modal.appendChild(modalContent);
                
                // Remove any existing modals
                const existingModal = document.querySelector('.modal');
                if (existingModal) {
                    document.body.removeChild(existingModal);
                }
                
                document.body.appendChild(modal);
                
                // Close modal when clicking outside
                window.onclick = (event) => {
                    if (event.target === modal) {
                        document.body.removeChild(modal);
                    }
                };
                
                addLogEntry('Successfully loaded full log', 'complete');
            } else {
                throw new Error(data.message || 'Failed to load logs');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            addLogEntry(`Error loading logs: ${error.message}`, 'error');
            
            // Show error in a modal instead of an alert
            const modal = document.createElement('div');
            modal.className = 'modal';
            
            const modalContent = document.createElement('div');
            modalContent.className = 'modal-content';
            
            const closeButton = document.createElement('span');
            closeButton.className = 'close-button';
            closeButton.textContent = '×';
            closeButton.onclick = () => {
                document.body.removeChild(modal);
            };
            
            const heading = document.createElement('h2');
            heading.textContent = 'Error Loading Logs';
            heading.style.color = '#dc3545';
            
            const errorMessage = document.createElement('p');
            errorMessage.textContent = error.message;
            errorMessage.style.color = '#721c24';
            errorMessage.style.backgroundColor = '#f8d7da';
            errorMessage.style.padding = '10px';
            errorMessage.style.borderRadius = '4px';
            
            const debugInfo = document.createElement('pre');
            debugInfo.textContent = `Time: ${new Date().toISOString()}\nError: ${error.stack || error.message}`;
            debugInfo.style.fontSize = '12px';
            debugInfo.style.marginTop = '10px';
            debugInfo.style.padding = '10px';
            debugInfo.style.backgroundColor = '#f8f9fa';
            
            modalContent.appendChild(closeButton);
            modalContent.appendChild(heading);
            modalContent.appendChild(errorMessage);
            modalContent.appendChild(debugInfo);
            modal.appendChild(modalContent);
            
            // Remove any existing modals
            const existingModal = document.querySelector('.modal');
            if (existingModal) {
                document.body.removeChild(existingModal);
            }
            
            document.body.appendChild(modal);
            
            // Close modal when clicking outside
            window.onclick = (event) => {
                if (event.target === modal) {
                    document.body.removeChild(modal);
                }
            };
        });
    }

    function addLogEntry(message, status = '', isSubstep = false, parentId = null) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        
        const timestamp = new Date().toLocaleTimeString();
        
        if (!isSubstep) {
            entry.id = 'log_' + Date.now();
            entry.innerHTML = `
                <span class="disclosure-triangle">▶</span>
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-step">${message}</span>
                ${status ? `<span class="log-status ${status}">${status}</span>` : ''}
                <div class="substeps"></div>
            `;
            
            entry.addEventListener('click', () => {
                entry.classList.toggle('expanded');
            });
            
            logEntries.appendChild(entry);
        } else if (parentId) {
            const parent = document.getElementById(parentId);
            if (parent) {
                const substeps = parent.querySelector('.substeps');
                const substep = document.createElement('div');
                substep.className = 'log-entry substep';
                substep.innerHTML = `
                    <span class="log-timestamp">${timestamp}</span>
                    <span class="log-step">${message}</span>
                    ${status ? `<span class="log-status ${status}">${status}</span>` : ''}
                `;
                substeps.appendChild(substep);
                parent.classList.add('has-substeps');
            }
        }
        
        logContainer.scrollTop = logContainer.scrollHeight;
        return entry.id;
    }

    function forceArchitecture(arch) {
        if (!selectedEmbyPath) {
            alert('Please select Emby Server path first');
            return;
        }

        if (!confirm(`Are you sure you want to force ${arch} architecture? This is for testing purposes only.`)) {
            return;
        }

        addLogEntry(`Forcing ${arch} architecture for testing...`, 'active');
        
        fetch('/api/force-test-mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                path: selectedEmbyPath,
                architecture: arch
            })
        })
        .then(response => response.json())
        .then(data => {
            const statusElement = document.getElementById('test-mode-status');
            if (data.success) {
                statusElement.textContent = '✅ ' + data.message;
                statusElement.className = 'status-message success';
                addLogEntry(`Forcing ${arch} architecture...`, 'complete');
                addLogEntry(data.message);
                
                // After forcing architecture, re-check compatibility
                setTimeout(checkCompatibility, 1000);
            } else {
                statusElement.textContent = '❌ ' + data.message;
                statusElement.className = 'status-message error';
                addLogEntry(`Forcing ${arch} architecture...`, 'error');
                addLogEntry(data.message, 'error');
            }
            
            statusElement.classList.remove('hidden');
        })
        .catch(error => {
            console.error('Error:', error);
            const statusElement = document.getElementById('test-mode-status');
            statusElement.textContent = '❌ An error occurred while forcing architecture';
            statusElement.className = 'status-message error';
            statusElement.classList.remove('hidden');
            addLogEntry(`Error: ${error.message}`, 'error');
        });
    }

    // Event listeners
    browseButton.addEventListener('click', function() {
        // First try to get list of servers
        fetch('/api/list-emby-servers')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.servers && data.servers.length > 0) {
                    // Clear and populate server list
                    serverList.innerHTML = '';
                    serverList.appendChild(new Option('Select Emby Server...', ''));
                    data.servers.forEach(server => {
                        serverList.appendChild(new Option(server, server));
                    });
                    
                    // Show server list
                    serverList.style.display = 'block';
                    serverList.focus();
                } else {
                    // If no servers found, fall back to file dialog
                    fetch('/api/browse-emby')
                        .then(response => response.json())
                        .then(data => {
                            if (data.success && data.path) {
                                embyPathInput.value = data.path;
                            } else {
                                console.error('Error selecting path:', data.message);
                            }
                        })
                        .catch(error => console.error('Error browsing:', error));
                }
            })
            .catch(error => console.error('Error listing servers:', error));
    });

    // Handle server selection
    serverList.addEventListener('change', function() {
        if (this.value) {
            embyPathInput.value = this.value;
            this.style.display = 'none';
        }
    });

    usePathButton.addEventListener('click', function() {
        const path = embyPathInput.value.trim();
        if (!path) {
            alert('Please enter a valid path');
            return;
        }

        addLogEntry('Validating Emby Server path...', 'info');
        selectEmbyPath(path)
            .then(() => {
                addLogEntry('Successfully validated path', 'success');
            })
            .catch(error => {
                addLogEntry(`Error: ${error.message}`, 'error');
                alert(error.message);
            });
    });

    checkCompatibilityButton.addEventListener('click', checkCompatibility);
    fixButton.addEventListener('click', fixFFMPEG);
    checkBackupButton.addEventListener('click', checkBackup);
    restoreButton.addEventListener('click', restoreFFMPEG);
    downloadLogButton.addEventListener('click', downloadLog);
    viewLogButton.addEventListener('click', viewFullLog);

    document.getElementById('force-x86-button').addEventListener('click', () => forceArchitecture('x86_64'));
    document.getElementById('force-arm-button').addEventListener('click', () => forceArchitecture('arm64'));
});
