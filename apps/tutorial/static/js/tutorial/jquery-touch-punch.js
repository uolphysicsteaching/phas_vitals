/*!
 * jQuery UI Touch Punch Fork 0.4.0
 *
 * Copyright 2011–2014, Dave Furfero
 * Dual licensed under the MIT or GPL Version 2 licenses.
 *
 * Depends:
 *  jquery.ui.widget.js
 *  jquery.ui.mouse.js
 */
(function(factory) {
  if (typeof define === 'function' && define.amd) {
    // AMD. Register as an anonymous module.
    define([
      'jquery',
      'jquery-ui/ui/widgets/mouse'
    ], factory);
  } else {
    // Browser globals
    factory(jQuery);
  }
}(function($) {

  // Detect touch support
  $.support.touch = 'ontouchend' in document || 'onpointerdown' in document || 'onMSPointerDown' in document;

  // Ignore browsers without touch support
  if (!$.support.touch) {
    return null;
  }

  var mouseProto = $.ui.mouse.prototype,
      _mouseInit = mouseProto._mouseInit,
      _mouseDestroy = mouseProto._mouseDestroy,
      touchHandled, touchTimer,
      dragIgnoreTime = 150, // When dragging less than 150ms we see it as a tap
      dragIgnoreDistance = 5, // When dragging less than 10px we see it as a tap unless longer than dragIgnoreTime
      longTapTime = 750; // LongTap tie in ms

  /**
   * Simulate a mouse event based on a corresponding touch event
   * @param {Object} event A touch event
   * @param {String} simulatedType The corresponding mouse event
   */
  function simulateMouseEvent (event, simulatedType) {

    // Ignore multi-touch events
    if (event.originalEvent.touches.length > 1) {
      return null;
    }

    var touch = event.originalEvent.changedTouches[0],
        simulatedEvent = document.createEvent('MouseEvents');

    if ($(touch.target).is("input") || $(touch.target).is("textarea")) {
      event.stopPropagation();
    } else {
      event.preventDefault();
    }

    // Initialize the simulated mouse event using the touch event's coordinates
    simulatedEvent.initMouseEvent(
      simulatedType,    // type
      true,             // bubbles
      true,             // cancelable
      window,           // view
      1,                // detail
      touch.screenX,    // screenX
      touch.screenY,    // screenY
      touch.clientX + $(window).scrollLeft(),    // clientX + scrollLeft - fix for zoomed devices while dragging
      touch.clientY + $(window).scrollTop(),    // clientY + scrollTop - fix for zoomed devices while dragging
      false,            // ctrlKey
      false,            // altKey
      false,            // shiftKey
      false,            // metaKey
      0,                // button
      null              // relatedTarget
    );

    // Dispatch the simulated event to the target element
    event.target.dispatchEvent(simulatedEvent);
  }

  /**
   * Handle the jQuery UI widget's touchstart events
   * @param {Object} event The widget element's touchstart event
   */
  mouseProto._touchStart = function (event) {

    var touch = event.originalEvent.changedTouches[0];

    // Track movement to determine if interaction was a click
    this._touchMoved = false;
    this._touchStartTime = new Date().getTime();
    this._touchStartX = touch.clientX;
    this._touchStartY = touch.clientY;

    // Ignore the event if another widget is already being handled
    if (touchHandled || !this._mouseCapture(touch)) {
      return null;
    }

    // Set the flag to prevent other widgets from inheriting the touch event
    touchHandled = true;

    // Simulate the mouseover event
    simulateMouseEvent(event, 'mouseover');

    // Simulate the mousemove event
    simulateMouseEvent(event, 'mousemove');

    // Simulate the mousedown event
    simulateMouseEvent(event, 'mousedown');

    // Start longTap timer
    touchTimer = setTimeout(function () {
      if (!this._touchMoved) {
        event.longTap = true;
        this._touchEnd(event);
      }
    }, longTapTime);
  };

  /**
   * Handle the jQuery UI widget's touchmove events
   * @param {Object} event The document's touchmove event
   */
  mouseProto._touchMove = function (event) {

    // Ignore event if not handled
    if (!touchHandled) {
      return null;
    }

    // Check if interaction was a click or a drag
    var touch = event.originalEvent.changedTouches[0];
    var holdingDownTime = new Date().getTime() - this._touchStartTime,
      movedX = Math.abs(touch.clientX - this._touchStartX),
      movedY = Math.abs(touch.clientY - this._touchStartY);
    if (holdingDownTime > dragIgnoreTime || movedX > dragIgnoreDistance || movedY > dragIgnoreDistance) {
      this._touchMoved = true;
    }

    // Simulate the mousemove event
    simulateMouseEvent(event, 'mousemove');
  };

  /**
   * Handle the jQuery UI widget's touchend events
   * @param {Object} event The document's touchend event
   */
  mouseProto._touchEnd = function (event) {

    // Ignore event if not handled
    if (!touchHandled) {
      return null;
    }

    // Simulate the mouseup event
    simulateMouseEvent(event, 'mouseup');

    // Simulate the mouseout event
    simulateMouseEvent(event, 'mouseout');

    // If the touch interaction did not move, it should trigger a click
    if (!this._touchMoved) {

      // Check if it was a long tap or regular tap
      if (event.longTap) {
        // Simulate the right-click event
        simulateMouseEvent(event, 'contextmenu');

      } else {
        // Simulate the click event
        simulateMouseEvent(event, 'click');
      }
    }

    // Unset the flag to allow other widgets to inherit the touch event
    clearTimeout(touchTimer);
    touchHandled = false;
  };

  /**
   * A duck punch of the $.ui.mouse _mouseInit method to support touch events.
   * This method extends the widget with bound touch event handlers that
   * translate touch events to mouse events and pass them to the widget's
   * original mouse event handling methods.
   */
  mouseProto._mouseInit = function () {

    // Delegate the touch handlers to the widget's element
    this.element.on({
        'touchstart': $.proxy(this, '_touchStart'),
        'touchmove': $.proxy(this, '_touchMove'),
        'touchend': $.proxy(this, '_touchEnd')
    });

    if(navigator.userAgent.match("MSIE")){
      this.element.css('-ms-touch-action', 'none');
    }

    // Call the original $.ui.mouse init method
    _mouseInit.call(this);
  };

  /**
   * Remove the touch event handlers
   */
  mouseProto._mouseDestroy = function () {

    // Delegate the touch handlers to the widget's element
    this.element.off({
      'touchstart': $.proxy(this, '_touchStart'),
      'touchmove': $.proxy(this, '_touchMove'),
      'touchend': $.proxy(this, '_touchEnd')
    });

    // Call the original $.ui.mouse destroy method
    _mouseDestroy.call(this);
  };
  return $;
}));
