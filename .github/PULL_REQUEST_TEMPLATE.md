name: Pull Request
description: Create a pull request for this project
labels: ["triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for contributing to MultiCode! Please fill out the information below to help us review your PR.

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Briefly describe the changes in this PR.
    validations:
      required: true

  - type: textarea
    id: related-issue
    attributes:
      label: Related Issue
      description: Link to the related issue(s) using `#issue-number` or `Fixes #issue-number`.
      placeholder: Fixes #123
    validations:
      required: false

  - type: dropdown
    id: type
    attributes:
      label: Type of Change
      description: What type of change is this?
      options:
        - Bug fix (non-breaking change that fixes an issue)
        - New feature (non-breaking change that adds functionality)
        - Breaking change (fix or feature that would cause existing functionality to change)
        - Documentation update
        - Code refactoring
        - Performance improvement
        - Test addition
        - Other (please describe)
    validations:
      required: true

  - type: textarea
    id: testing
    attributes:
      label: How Has This Been Tested?
      description: Describe the tests you ran to verify your changes.
      placeholder: |
        - [ ] Ran existing tests
        - [ ] Added new tests
        - [ ] Tested manually
    validations:
      required: true

  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      description: Please ensure your PR meets the following requirements.
      options:
        - label: My code follows the style guidelines (PEP 8, Black formatting)
          required: true
        - label: I have performed a self-review of my code
          required: true
        - label: I have commented my code, particularly in hard-to-understand areas
          required: true
        - label: I have updated the documentation accordingly
          required: false
        - label: My changes generate no new warnings
          required: true
        - label: I have added tests that prove my fix/feature works
          required: true
        - label: All tests pass locally (`pytest`)
          required: true
        - label: Coverage has not decreased
          required: true

  - type: textarea
    id: screenshots
    attributes:
      label: Screenshots
      description: If applicable, add screenshots to help explain your changes.
    validations:
      required: false

  - type: textarea
    id: additional-context
    attributes:
      label: Additional Context
      description: Add any other context about the PR here.
    validations:
      required: false

  - type: checkboxes
    id: terms
    attributes:
      label: Code of Conduct
      description: By submitting this pull request, you agree to follow our [Code of Conduct](../CODE_OF_CONDUCT.md).
      options:
        - label: I agree to follow this project's Code of Conduct
          required: true
