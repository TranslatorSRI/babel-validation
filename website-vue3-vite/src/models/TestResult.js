/**
 * A class representing the result of a test.
 */
export class TestResult {
    /** Construct a TestResult based largely on a JSON result from . */
    constructor(status, message, resultType = "null", result = {}) {
        this.status = status;
        this.message = message;
        this.resultType = resultType;
        this.result = result;
    }

    /** Create a TestResult for a success. */
    static success(message, resultType = "unknown", result = null) {
        return new TestResult(true, message, resultType, result);
    }

    /** Create a TestResult for a failure. */
    static failure(message, resultType = "unknown", result = null) {
        return new TestResult(false, message, resultType, result);
    }
}