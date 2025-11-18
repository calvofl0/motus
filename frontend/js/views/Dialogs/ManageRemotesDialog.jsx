import React from 'react';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import Icon from 'components/Icon.jsx';

class ManageRemotesDialog extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            step: 1, // 1: remotes list, 2: templates list, 3: form
            remotes: [],
            templates: [],
            templatesAvailable: false,
            selectedTemplate: null,
            formValues: {},
            remoteName: '',
            loading: false,
            error: null,
            token: '',
        };
    }

    componentDidMount() {
        // Get token from URL params or cookie
        const urlParams = new URLSearchParams(window.location.search);
        const tokenFromUrl = urlParams.get('token');
        const tokenFromCookie = this.getCookie('motus_token');
        const token = tokenFromUrl || tokenFromCookie || '';

        this.setState({ token }, () => {
            this.loadRemotes();
            this.loadTemplates();
        });
    }

    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    async loadRemotes() {
        try {
            const response = await fetch('/api/remotes', {
                headers: {
                    'Authorization': `token ${this.state.token}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to load remotes');
            }

            const data = await response.json();
            this.setState({ remotes: data.remotes || [] });
        } catch (error) {
            this.setState({ error: error.message });
        }
    }

    async loadTemplates() {
        try {
            const response = await fetch('/api/templates', {
                headers: {
                    'Authorization': `token ${this.state.token}`,
                },
            });

            if (!response.ok) {
                throw new Error('Failed to load templates');
            }

            const data = await response.json();
            this.setState({
                templates: data.templates || [],
                templatesAvailable: data.available || false,
            });
        } catch (error) {
            this.setState({ error: error.message });
        }
    }

    async deleteRemote(remoteName) {
        if (!confirm(`Are you sure you want to delete the remote "${remoteName}"?`)) {
            return;
        }

        this.setState({ loading: true, error: null });

        try {
            const response = await fetch(`/api/remotes/${remoteName}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `token ${this.state.token}`,
                },
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete remote');
            }

            // Reload remotes list
            await this.loadRemotes();
            this.setState({ loading: false });
        } catch (error) {
            this.setState({ error: error.message, loading: false });
        }
    }

    async addRemote() {
        this.setState({ loading: true, error: null });

        try {
            const { selectedTemplate, formValues, remoteName } = this.state;

            const requestBody = {
                name: remoteName,
                template: selectedTemplate.name,
                values: formValues,
            };

            const response = await fetch('/api/remotes', {
                method: 'POST',
                headers: {
                    'Authorization': `token ${this.state.token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to add remote');
            }

            // Success - reload remotes and go back to step 1
            await this.loadRemotes();
            this.setState({
                step: 1,
                selectedTemplate: null,
                formValues: {},
                remoteName: '',
                loading: false,
            });
        } catch (error) {
            this.setState({ error: error.message, loading: false });
        }
    }

    handleClose() {
        this.props.onClose();
    }

    handleAddClick() {
        this.setState({ step: 2, error: null });
    }

    handleTemplateSelect(template) {
        this.setState({ selectedTemplate: template });
    }

    handleNext() {
        const { step, selectedTemplate } = this.state;

        if (step === 2 && selectedTemplate) {
            // Move to form step
            this.setState({ step: 3, error: null });
        }
    }

    handleBack() {
        const { step } = this.state;

        if (step === 2) {
            this.setState({ step: 1, selectedTemplate: null, error: null });
        } else if (step === 3) {
            this.setState({ step: 2, formValues: {}, remoteName: '', error: null });
        }
    }

    handleFormChange(field, value) {
        this.setState(prevState => ({
            formValues: {
                ...prevState.formValues,
                [field]: value,
            },
        }));
    }

    handleRemoteNameChange(value) {
        this.setState({ remoteName: value });
    }

    handleFormSubmit(event) {
        event.preventDefault();
        this.addRemote();
    }

    renderStep1() {
        const { remotes, loading, templatesAvailable } = this.state;

        return (
            <React.Fragment>
                <Modal.Header closeButton>
                    <Modal.Title>Manage Remotes</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div className="container">
                        {this.state.error && (
                            <Alert variant="danger" onClose={() => this.setState({ error: null })} dismissible>
                                {this.state.error}
                            </Alert>
                        )}
                        <div className="row mb-3">
                            <div className="col-12">
                                <div className="d-flex justify-content-between align-items-center mb-2">
                                    <h5>Configured Remotes</h5>
                                    {templatesAvailable && (
                                        <Button
                                            variant="success"
                                            size="sm"
                                            onClick={() => this.handleAddClick()}
                                            disabled={loading}
                                        >
                                            <Icon name="plus" /> Add Remote
                                        </Button>
                                    )}
                                </div>
                                {remotes.length === 0 ? (
                                    <p className="text-muted">No remotes configured</p>
                                ) : (
                                    <Table striped bordered hover size="sm">
                                        <thead>
                                            <tr>
                                                <th>Name</th>
                                                <th>Type</th>
                                                <th style={{ width: '80px' }}>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {remotes.map(remote => (
                                                <tr key={remote.name}>
                                                    <td>{remote.name}</td>
                                                    <td>{remote.type}</td>
                                                    <td>
                                                        <Button
                                                            variant="danger"
                                                            size="sm"
                                                            onClick={() => this.deleteRemote(remote.name)}
                                                            disabled={loading}
                                                            title="Delete remote"
                                                        >
                                                            <Icon name="dash" />
                                                        </Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </Table>
                                )}
                            </div>
                        </div>
                    </div>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => this.handleClose()}>
                        Close
                    </Button>
                </Modal.Footer>
            </React.Fragment>
        );
    }

    renderStep2() {
        const { templates, selectedTemplate } = this.state;

        return (
            <React.Fragment>
                <Modal.Header closeButton>
                    <Modal.Title>Select Template</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div className="container">
                        {this.state.error && (
                            <Alert variant="danger" onClose={() => this.setState({ error: null })} dismissible>
                                {this.state.error}
                            </Alert>
                        )}
                        <div className="row">
                            <div className="col-12">
                                <p>Select a template for the new remote:</p>
                                <div className="list-group">
                                    {templates.map(template => (
                                        <button
                                            key={template.name}
                                            type="button"
                                            className={`list-group-item list-group-item-action ${
                                                selectedTemplate?.name === template.name ? 'active' : ''
                                            }`}
                                            onClick={() => this.handleTemplateSelect(template)}
                                        >
                                            <strong>{template.name}</strong>
                                            <br />
                                            <small>
                                                Fields: {template.fields.map(f => f.label).join(', ')}
                                            </small>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => this.handleBack()}>
                        Back
                    </Button>
                    <Button
                        variant="primary"
                        onClick={() => this.handleNext()}
                        disabled={!selectedTemplate}
                    >
                        Next
                    </Button>
                </Modal.Footer>
            </React.Fragment>
        );
    }

    renderStep3() {
        const { selectedTemplate, remoteName, formValues, loading } = this.state;

        if (!selectedTemplate) {
            return null;
        }

        const allFieldsFilled = remoteName && selectedTemplate.fields.every(
            field => formValues[field.label]
        );

        return (
            <React.Fragment>
                <Modal.Header closeButton>
                    <Modal.Title>Configure Remote</Modal.Title>
                </Modal.Header>
                <form onSubmit={(event) => this.handleFormSubmit(event)}>
                    <Modal.Body>
                        <div className="container">
                            {this.state.error && (
                                <Alert variant="danger" onClose={() => this.setState({ error: null })} dismissible>
                                    {this.state.error}
                                </Alert>
                            )}
                            <div className="row">
                                <div className="col-12">
                                    <p>Template: <strong>{selectedTemplate.name}</strong></p>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Remote Name</Form.Label>
                                        <Form.Control
                                            type="text"
                                            placeholder="Enter remote name"
                                            value={remoteName}
                                            onChange={(e) => this.handleRemoteNameChange(e.target.value)}
                                            required
                                            pattern="[a-zA-Z0-9_-]+"
                                            title="Use only letters, numbers, underscores, and hyphens"
                                        />
                                        <Form.Text className="text-muted">
                                            Use only letters, numbers, underscores, and hyphens
                                        </Form.Text>
                                    </Form.Group>
                                    {selectedTemplate.fields.map(field => (
                                        <Form.Group key={field.key} className="mb-3">
                                            <Form.Label>{field.label}</Form.Label>
                                            <Form.Control
                                                type={field.label.toLowerCase().includes('password') || field.label.toLowerCase().includes('secret') || field.label.toLowerCase().includes('key') ? 'password' : 'text'}
                                                placeholder={`Enter ${field.label}`}
                                                value={formValues[field.label] || ''}
                                                onChange={(e) => this.handleFormChange(field.label, e.target.value)}
                                                required
                                            />
                                        </Form.Group>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={() => this.handleBack()} disabled={loading}>
                            Back
                        </Button>
                        <Button
                            variant="primary"
                            type="submit"
                            disabled={!allFieldsFilled || loading}
                        >
                            {loading ? 'Creating...' : 'Create Remote'}
                        </Button>
                    </Modal.Footer>
                </form>
            </React.Fragment>
        );
    }

    render() {
        const { step } = this.state;

        return (
            <div className='dialog-manage-remotes'>
                <Modal
                    show={true}
                    size="lg"
                    onHide={() => this.handleClose()}
                >
                    {step === 1 && this.renderStep1()}
                    {step === 2 && this.renderStep2()}
                    {step === 3 && this.renderStep3()}
                </Modal>
            </div>
        );
    }
}

ManageRemotesDialog.defaultProps = {
    onClose: () => {},
};

import {connect} from 'react-redux';
import {hideManageRemotesDialog} from 'actions/dialogActions.jsx';

const mapStateToProps = state => ({
});

const mapDispatchToProps = dispatch => ({
    onClose: () => dispatch(hideManageRemotesDialog()),
});

export default connect(mapStateToProps, mapDispatchToProps)(ManageRemotesDialog);
